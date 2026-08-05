#!/usr/bin/env python3
"""
07_diagnose_synthetic.py — Contrôle "GBM à fenêtres réalistes" vs données réelles.
===============================================================================
RATTACHEMENT : H4. Diagnostic SEUL (ne modifie pas le contrat H1–H5).

  Question : le FAIL du bucket vol 1 est-il un artefact de la MACHINERIE
  (estimation, fenêtres, simulateur, test) ou une propriété des CHEMINS réels ?

  Test : on reconstruit un jeu SYNTHÉTIQUE dont chaque fenêtre de test a les
  (μ̂, σ̂) RÉALISÉS des données réelles (random walk GBM à paramètres variant
  par fenêtre, seed fixée). La machinerie de validation voit exactement les
  mêmes régimes que sur le réel, mais des chemins GBM purs.
    - Si ce contrôle PASSE : la machinerie est saine avec des fenêtres
      non-stationnaires ; le FAIL réel vient de la structure des chemins.
    - S'il échoue de la même façon : la non-stationnarité des (μ, σ) par
      fenêtre, telle que traitée par la validation, explique le FAIL.

  Variante structurelle : on simule aussi un GBM de MÊME vol par fenêtre mais
  avec une volatilité réalisée lissée (EWMA) intra-fenêtre, pour séparer le
  clustering de vol de la pure non-stationnarité de niveau.

Usage :
  python scripts/07_diagnose_synthetic.py [--seed S]
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.data_loader import load_with_provenance
from src.risk.moments import estimate_moments
from src.simulator.engine import bars_from_frame
from src.simulator.runner import RunConfig, run_backtest
from src.strategy.grid_short import GridConfig, ShortGridStrategy
from src.validation.thesis import predict_discrete, validate_thesis
from src.validation.windows import build_windows

REAL_PATH = Path("data/raw/SOLUSDT_1h.csv")
L, S, MMR = 5.0, 0.02, 0.0050
STEPS = 30
N_TRAIN, N_TEST = 2000, 1000


def build_real_hlc_moments(df) -> tuple[np.ndarray, np.ndarray]:
    """Par fenêtre de test : (μ̂, σ̂) réalisés sur les rendements logs du close."""
    closes = df["close"].to_numpy(dtype=float)
    windows = build_windows(len(closes), N_TRAIN, N_TEST)
    mu_w, sig_w = [], []
    for w in windows:
        em = estimate_moments(closes[w.test_start:w.test_end])
        mu_w.append(em.mu)
        sig_w.append(em.sigma)
    return np.array(mu_w), np.array(sig_w)


def gbm_with_window_params(n: int, windows, mu_w, sig_w, seed: int) -> np.ndarray:
    """Random walk GBM : chaque fenêtre de test tire ses (μ, σ) réalisés réels.

    Les rendements sont gaussiens de moyenne/variance fixées par fenêtre (pas
    de clustering intra-fenêtre, pas de queues). Le train (2000 premières
    barres) est simulé avec les moments du train réel.
    """
    rng = np.random.default_rng(seed)
    logp = np.zeros(n)
    mu_by_i = np.full(n, mu_w[0] * 0.0)
    sig_by_i = np.full(n, sig_w[0] * 0.0)
    # region train : moments réels de la 1re fenêtre de train
    closes_real, _ = load_with_provenance(str(REAL_PATH))
    closes_real = closes_real["close"].to_numpy(dtype=float)
    em0 = estimate_moments(closes_real[:N_TRAIN])
    mu_by_i[:N_TRAIN] = em0.mu
    sig_by_i[:N_TRAIN] = em0.sigma
    for w, (mu, sig) in zip(windows, zip(mu_w, sig_w)):
        mu_by_i[w.test_start:w.test_end] = mu
        sig_by_i[w.test_start:w.test_end] = sig
    # remplir les queues non couvertes (après la dernière fenêtre)
    last = windows[-1]
    mu_by_i[last.test_end:] = mu_w[-1]
    sig_by_i[last.test_end:] = sig_w[-1]
    r = rng.normal(mu_by_i, sig_by_i)
    logp = np.cumsum(r)
    return np.exp(logp)


def to_ohlc(price: np.ndarray, steps: int = STEPS, seed: int = 1) -> pd.DataFrame:
    """OHLC horaire à partir de closes (pont brownien intra-barre), sémantique
    identique à generate_gbm_hourly_ohlc (mêmes extrêmes high/low)."""
    rng = np.random.default_rng(seed)
    delta = np.log(price[1:] / price[:-1])
    opens = price[:-1].copy()
    closes = price[1:]
    highs = np.zeros(len(closes))
    lows = np.zeros(len(closes))
    for j in range(len(delta)):
        u = rng.normal(0.0, 1.0 / np.sqrt(steps), (1, steps))
        U = np.cumsum(u, axis=1)
        bridge = U - (np.arange(1, steps + 1) / steps) * U[:, -1:]
        logpath = bridge[0]
        highs[j] = opens[j] * np.exp(logpath.max())
        lows[j] = opens[j] * np.exp(logpath.min())
    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": closes,
    })
    return df


def run_validate(df, label: str) -> int:
    closes = df["close"].to_numpy(dtype=float)
    bars = bars_from_frame(df)
    windows = build_windows(len(bars), N_TRAIN, N_TEST)
    grid_cfg = GridConfig(grid_size=1, grid_ratio=S, qty_sol=10.0, leverage=L)
    run_cfg = RunConfig(initial_capital=10_000.0)
    predictor = partial(predict_discrete, steps_per_hour=STEPS,
                        n_paths=20_000, seed=0)
    report = validate_thesis(closes, bars, windows, grid_cfg,
                             run_cfg=run_cfg, predictor=predictor)
    print(f"\n=== {label} ===")
    print(report.summary())
    print(f"  ouvertes en fin de jeu (censurées, V7) : {report.n_open_at_end}   "
          f"résolues hors fenêtre : {report.n_hors_fenetres}   "
          f"skips : {report.n_skipped}")
    return 0 if report.passes else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=60)
    args = ap.parse_args()

    df_real, meta = load_with_provenance(str(REAL_PATH))
    n = len(df_real)
    mu_w, sig_w = build_real_hlc_moments(df_real)
    windows = build_windows(n, N_TRAIN, N_TEST)
    print(f"Réel : {meta['source']} — {n} barres, {len(windows)} fenêtres")

    # 1) GBM à paramètres réalistes par fenêtre (chemin pur)
    price = gbm_with_window_params(n, windows, mu_w, sig_w, seed=args.seed)
    df = to_ohlc(price, seed=args.seed + 1)
    rc1 = run_validate(df, f"GBM fenêtres-réalistes (seed {args.seed})")
    print(f"  → exit={rc1}")

    # 2) le contrôle originel (GBM homogène) pour référence
    from data.synthetic_gbm import generate_gbm_hourly_ohlc
    df0 = generate_gbm_hourly_ohlc(n_hours=n, mu_hourly=0.0002,
                                   sigma_hourly=0.025, steps_per_hour=STEPS,
                                   seed=args.seed)
    rc0 = run_validate(df0, f"GBM homogène (seed {args.seed}, contrôle d'origine)")
    print(f"  → exit={rc0}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
