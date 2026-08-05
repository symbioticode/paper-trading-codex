"""
thesis.py — Validation hors-échantillon H4 (le cœur de la thèse).
===============================================================================
RATTACHEMENT : H4 (prédiction de la fréquence de liquidation), H2 (formule),
              M1 (estimation), simulateur (engine E6), windows (W1–W3).

  Protocole :
    V1  La stratégie tourne en continu sur toutes les barres (grid SHORT, L et s
        fixés). Chaque position est attribuée à la fenêtre de test où elle
        s'ouvre (W3). Le runner REDIMENSIONNE les signaux (R5) : aucune
        position n'est écartée pour cash/cap → pas de biais de sélection.
    V2  Pour chaque fenêtre de test, (μ̂, σ̂) est estimé sur la fenêtre
        d'apprentissage précédente (M1) et P(liq) prédit.
    V3  PRÉDICTION : le simulateur surveille les barrières par barre OHLC
        horaire (E6), pas en temps continu. La formule continue H2 ignore ce
        biais de granularité (mesuré : +1,5 à +2 pts à L=5, s=2%, σ=2,5%). La
        prédiction H4 est donc le Monte Carlo DISCRET aux sémantiques du
        simulateur (`simulate_two_barrier_bars`, pont brownien intra-barre).
    V4  Buckets de RÉGIME par volatilité d'apprentissage (terciles).
    V5  TEST — CORRECTION DE DÉPENDANCE (MESURÉE sur le contrôle GBM) : les
        positions d'une même fenêtre partagent le MÊME chemin de prix : leurs
        issues ne sont PAS indépendantes. Le CI binomial naïf sur-réjette
        (~3x sur le contrôle). Le test H4 est un WALD CLUSTER-ROBUSTE,
        cluster = fenêtre, variance de la dispersion OBSERVÉE :
            V_rob = (W/(W−1)) · Σ_w (n_w/N)²·(p̂_w − p̂)²
        et on accepte si |p̂ − P̂| ≤ t(0,975, W−1)·√V_rob, où
        P̂ = Σ n_w·P̂_w/N. (Un sandwich sur les résidus p̂_w − P̂_w serait
        aveugle à un biais systématique — rejeté en J6.)
        Calibration mesurée sur 20 seeds du contrôle : global 0/20, buckets
        4/60, PASS global ≈ 80% = 0.95⁴ (4 tests indépendants à 95%).
    V6  PASS si le GLOBAL est accepté ET chaque bucket non vide l'est (V5) ET
        aucun skip cash/cap. Buckets non testables (n=0 ou W<2) : signalés.
    V7  Positions jamais résolues en fin de jeu : censurées, comptées
        (n_censored) et signalées — jamais ajoutées au dénominateur.

  RATTACHEMENT : ne PAS confondre cette validation (fréquence de liq) avec la
  rentabilité : le PnL est un constat mesuré séparé (benchmarks).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

import numpy as np
from scipy import stats as st

from src.risk.moments import estimate_moments
from src.risk.monte_carlo import simulate_two_barrier_bars
from src.risk.two_barriers import prob_liquidation_from_L
from src.simulator.engine import Bar, SimulationEngine
from src.simulator.runner import RunConfig, run_backtest
from src.strategy.grid_short import GridConfig, ShortGridStrategy
from src.validation.windows import Window, tag_opening_indices

Predictor = Callable[[float, float, float, float], float]   # (μ, σ, L, s) → P


def predict_discrete(
    mu: float,
    sigma: float,
    leverage: float,
    s: float,
    mmr: float = 0.0050,
    steps_per_hour: int = 30,
    n_paths: int = 20_000,
    seed: int = 0,
) -> float:
    """V3 : P(liq) discrète aux sémantiques du simulateur (MC déterministe)."""
    d = (1.0 / leverage - mmr) / (1.0 + mmr)
    a = -math.log(1.0 - s)
    b = math.log(1.0 + d)
    gt = simulate_two_barrier_bars(
        mu, sigma, a, b, n=n_paths,
        steps_per_hour=steps_per_hour, cap=100_000, seed=seed,
    )
    return gt.p_hat


def cluster_robust_test(
    k_w: Sequence[int],
    n_w: Sequence[int],
    pred_w: Sequence[float],
    alpha: float = 0.05,
) -> tuple[float, float, float, float, bool]:
    """V5 : Wald cluster-robuste (cluster = fenêtre) de H0 : E[p̂_w] = P̂_w.

    La variance sandwich mesure la dispersion OBSERVÉE entre fenêtres,
    indépendamment du modèle :
        V_rob = (W/(W−1)) · Σ_w (n_w/N)²·(p̂_w − p̂)²
    C'est ce qui rend le test PUISSANT contre un biais systématique : un écart
    constant du modèle gonfle |p̂ − P̂| sans gonfler V. (Un sandwich évalué sur
    les résidus p̂_w − P̂_w serait aveugle à un tel biais — rejeté en J6.)

    Retourne (p̂, P̂, V_rob, t_crit·√V_rob, accepté).
    Exige W ≥ 2 fenêtres ; sinon le test n'est pas possible (accepté=False).
    """
    k_w = list(k_w)
    n_w = list(n_w)
    pred_w = list(pred_w)
    if len(k_w) != len(n_w) or len(n_w) != len(pred_w):
        raise ValueError("k_w, n_w, pred_w doivent avoir la même longueur.")
    for k, n in zip(k_w, n_w):
        if k < 0 or n < 0 or k > n:
            raise ValueError(f"Comptes invalides : k={k}, n={n}")
    # Les fenêtres SANS position (n=0) ne contribuent à rien : on les écarte
    # du test (elles ne peuvent ni apporter de variance, ni de masse).
    active = [i for i, n in enumerate(n_w) if n > 0]
    if not active:
        W = len(n_w)
        N = 0
    else:
        W = len(active)
        N = int(sum(n_w[i] for i in active))
        k_w = [k_w[i] for i in active]
        n_w = [n_w[i] for i in active]
        pred_w = [pred_w[i] for i in active]
    if N == 0 or W < 2:
        return float("nan"), float("nan"), float("nan"), float("nan"), False

    p = sum(k_w) / N
    pred = sum(n_w[i] * pred_w[i] for i in range(W)) / N
    disp = sum((n_w[i] / N) ** 2 * (k_w[i] / n_w[i] - p) ** 2 for i in range(W))
    v_rob = disp * W / (W - 1.0)
    t_crit = st.t.ppf(1.0 - alpha / 2.0, W - 1)
    margin = t_crit * math.sqrt(v_rob)
    return p, pred, v_rob, margin, abs(p - pred) <= margin


@dataclass(frozen=True)
class WindowResult:
    id: int
    mu_train: float
    sigma_train: float
    p_pred: float          # prédiction discrète (V3)
    p_pred_cont: float     # formule continue H2 (référence, non utilisée)
    n_positions: int
    k_liquidations: int


@dataclass(frozen=True)
class BucketResult:
    bucket: int
    n: int
    k: int
    p_obs: float
    p_pred: float
    margin: float          # t·√V_rob (0 si non testable)
    testable: bool
    accepted: bool


@dataclass
class ThesisReport:
    windows: List[WindowResult]
    buckets: List[BucketResult]
    global_bucket: BucketResult
    n_censored: int
    n_skipped: int
    passes: bool

    def summary(self) -> str:
        lines = []
        for b in self.buckets:
            if not b.testable:
                lines.append(f"  bucket vol {b.bucket}: NON TESTABLE (n={b.n})")
                continue
            lines.append(
                f"  bucket vol {b.bucket}: n={b.n:5d} k={b.k:4d} "
                f"p̂={b.p_obs:.4f} P̂={b.p_pred:.4f} "
                f"±{b.margin:.4f} (t·√V_rob) {'OK' if b.accepted else 'HORS'}"
            )
        g = self.global_bucket
        lines.append(
            f"  global: n={g.n} k={g.k} p̂={g.p_obs:.4f} P̂={g.p_pred:.4f} "
            f"±{g.margin:.4f} (t·√V_rob) {'OK' if g.accepted else 'HORS'}"
        )
        head = "PASS" if self.passes else "FAIL"
        return f"{head}\n" + "\n".join(lines)


def _bucket_id(value: float, thresholds: Sequence[float]) -> int:
    for i, t in enumerate(thresholds):
        if value <= t:
            return i
    return len(thresholds)


def validate_thesis(
    closes: np.ndarray,
    bars: Sequence[Bar],
    windows: Sequence[Window],
    grid_cfg: GridConfig,
    run_cfg: Optional[RunConfig] = None,
    alpha: float = 0.05,
    predictor: Optional[Predictor] = None,
) -> ThesisReport:
    """V1–V7 : protocole complet de validation H4.

    `predictor(μ, σ, L, s) → P` : par défaut `predict_discrete` (V3). On peut
    injecter la formule continue H2 pour mesurer le biais de granularité.
    """
    closes = np.asarray(closes, dtype=float)
    if len(closes) != len(bars):
        raise ValueError("closes et bars doivent avoir la même longueur.")
    if predictor is None:
        predictor = predict_discrete

    res = run_backtest(list(bars), ShortGridStrategy(grid_cfg), cfg=run_cfg)
    engine: SimulationEngine = res.engine

    ts_to_idx = {bar.ts: i for i, bar in enumerate(bars)}
    opening = [ts_to_idx[t.opened_at] for t in engine.trades]
    win_of = tag_opening_indices(opening, windows)

    # stats par fenêtre
    wid_set = {w.id for w in windows}
    est_by_win: dict[int, tuple[float, float]] = {}
    for w in windows:
        est = estimate_moments(closes[w.train_start:w.train_end])
        est_by_win[w.id] = (est.mu, est.sigma)

    n_censored = 0
    n_by_win = {w.id: 0 for w in windows}
    k_by_win = {w.id: 0 for w in windows}
    for i, t in enumerate(engine.trades):
        w = win_of[i]
        if w in wid_set:
            n_by_win[w] += 1
            if t.reason == "liquidation":
                k_by_win[w] += 1
        else:
            n_censored += 1

    window_results: List[WindowResult] = []
    for w in windows:
        mu, sigma = est_by_win[w.id]
        window_results.append(WindowResult(
            id=w.id, mu_train=mu, sigma_train=sigma,
            p_pred=predictor(mu, sigma, grid_cfg.leverage, grid_cfg.grid_ratio),
            p_pred_cont=prob_liquidation_from_L(
                grid_cfg.leverage, grid_cfg.grid_ratio, mu, sigma),
            n_positions=n_by_win[w.id], k_liquidations=k_by_win[w.id],
        ))

    # buckets par tercile de volatilité d'apprentissage
    sigma_thr = np.quantile([wr.sigma_train for wr in window_results], [1 / 3, 2 / 3])

    def make_bucket(sel: Sequence[WindowResult]) -> BucketResult:
        n_w = [wr.n_positions for wr in sel]
        k_w = [wr.k_liquidations for wr in sel]
        pred_w = [wr.p_pred for wr in sel]
        testable = sum(n_w) > 0 and len(n_w) >= 2
        if not testable:
            return BucketResult(
                bucket=-1, n=sum(n_w), k=sum(k_w), p_obs=float("nan"),
                p_pred=float("nan"), margin=0.0, testable=False, accepted=False)
        p, pred, _, margin, ok = cluster_robust_test(k_w, n_w, pred_w, alpha)
        return BucketResult(
            bucket=-1, n=sum(n_w), k=sum(k_w), p_obs=p, p_pred=pred,
            margin=margin, testable=True, accepted=ok)

    buckets: List[BucketResult] = []
    for b in range(len(sigma_thr) + 1):
        sel = [wr for wr in window_results if _bucket_id(wr.sigma_train, sigma_thr) == b]
        br = make_bucket(sel)
        buckets.append(BucketResult(
            bucket=b, n=br.n, k=br.k, p_obs=br.p_obs, p_pred=br.p_pred,
            margin=br.margin, testable=br.testable, accepted=br.accepted))

    global_bucket = make_bucket(window_results)

    passes = (
        global_bucket.testable and global_bucket.accepted
        and all(not b.testable or b.accepted for b in buckets)
        and res.n_skipped_cash == 0 and res.n_skipped_cap == 0
    )
    return ThesisReport(
        windows=window_results, buckets=buckets, global_bucket=global_bucket,
        n_censored=n_censored,
        n_skipped=res.n_skipped_cash + res.n_skipped_cap,
        passes=passes,
    )
