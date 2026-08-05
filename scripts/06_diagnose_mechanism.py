#!/usr/bin/env python3
"""
06_diagnose_mechanism.py — Mécanisme du FAIL H4 : régime vécu vs structure du chemin.
===============================================================================
RATTACHEMENT : H4. Diagnostic SEUL (ne modifie pas le contrat H1–H5).

  État connu (05) : re-prédire avec les moments RÉALISÉS de la fenêtre de test
  ne comble que la moitié de l'écart du bucket 1 (0.040 → 0.022). Reste à
  distinguer :
    (a) NON-STATIONNARITÉ DU RÉGIME : les positions vivent dans un régime de
        (μ, σ) différent de celui estimé sur la fenêtre d'apprentissage (et
        même du test moyen) ;
    (b) INADÉQUATION STRUCTURELLE : à (μ, σ) du régime vécu identiques, les
        chemins réels liquident moins qu'un GBM (queues, sauts, clustering,
        mémoire).

  MÉTHODE : pour chaque position, on mesure (μ̂_life, σ̂_life) sur la portion
  de chemin QU'ELLE A VÉCUE (de son ouverture à sa résolution), et on re-prédit
  P(liq | μ̂_life, σ̂_life). Agrégé sur le bucket :
    - si ΣP(σ̂_life) ≈ p̂ réel : le modèle est structurellement sain, le FAIL
      vient du régime vécu (a) ;
    - si ΣP(σ̂_life) ≫ p̂ réel : même avec le bon régime, le chemin réel
      liquide moins (b).

  CALIBRATION : le même calcul est fait sur le contrôle GBM (où le modèle est
  VRAI par construction). Si le contrôle montre aussi ΣP(σ̂_life) ≈ p̂, la
  méthode est valide et l'écart résiduel sur le réel est attribuable à (b).

  BIAS de sélection (documenté) : σ̂_life est mesuré de l'ouverture à la
  résolution — une position liquidée a vécu plus longtemps (et souvent plus de
  vol) qu'une position TP. C'est précisément le point : le modèle prédit à
  partir du régime d'APPRENTISSAGE, pas du régime VÉCU.

Usage :
  python scripts/06_diagnose_mechanism.py [--data real|gbm] [--seed S]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.data_loader import load_with_provenance
from data.synthetic_gbm import generate_gbm_hourly_ohlc
from src.risk.moments import estimate_moments, log_returns
from src.risk.monte_carlo import simulate_two_barrier_bars
from src.simulator.engine import bars_from_frame
from src.simulator.runner import RunConfig, run_backtest
from src.strategy.grid_short import GridConfig, ShortGridStrategy
from src.validation.thesis import _bucket_id
from src.validation.windows import build_windows, tag_opening_indices

REAL_PATH = Path("data/raw/SOLUSDT_1h.csv")
L, S, MMR = 5.0, 0.02, 0.0050
STEPS = 30
N_PATHS = 8_000
N_TRAIN, N_TEST = 2000, 1000


def mc_p(mu: float, sigma: float) -> float:
    d = (1.0 / L - MMR) / (1.0 + MMR)
    a = -np.log(1.0 - S)
    b = np.log(1.0 + d)
    gt = simulate_two_barrier_bars(mu, sigma, a, b, n=N_PATHS,
                                   steps_per_hour=STEPS, seed=0)
    return gt.p_hat


def run_diag(closes: np.ndarray, bars, label: str) -> None:
    n = len(bars)
    windows = build_windows(n, N_TRAIN, N_TEST)
    grid_cfg = GridConfig(grid_size=1, grid_ratio=S, qty_sol=10.0, leverage=L)
    run_cfg = RunConfig(initial_capital=10_000.0)

    res = run_backtest(list(bars), ShortGridStrategy(grid_cfg), cfg=run_cfg)
    engine = res.engine
    ts_to_idx = {bar.ts: i for i, bar in enumerate(bars)}
    win_of = tag_opening_indices([ts_to_idx[t.opened_at] for t in engine.trades],
                                 windows)
    wid_set = {w.id for w in windows}

    sig_tr_by_win = {w.id: estimate_moments(closes[w.train_start:w.train_end]).sigma
                     for w in windows}
    mu_tr_by_win = {w.id: estimate_moments(closes[w.train_start:w.train_end]).mu
                    for w in windows}
    sig_thr = np.quantile(list(sig_tr_by_win.values()), [1 / 3, 2 / 3])

    print(f"\n######## {label} ########")

    rows = []
    for i, t in enumerate(engine.trades):
        w = win_of[i]
        if w not in wid_set:
            continue
        oi = ts_to_idx[t.opened_at]
        ci = ts_to_idx.get(t.closed_at)
        censored = ci is None or ci <= oi
        ci = min(ci if ci and ci > oi else oi + 1, n - 1)
        life = log_returns(closes[oi:ci + 1])
        mu_life = float(life.mean())
        sig_life = float(life.std(ddof=1)) if len(life) > 1 else sig_tr_by_win[w]
        rows.append({
            "bucket": _bucket_id(sig_tr_by_win[w], sig_thr),
            "win": w,
            "sig_tr": sig_tr_by_win[w],
            "mu_tr": mu_tr_by_win[w],
            "sig_life": sig_life,
            "mu_life": mu_life,
            "life_h": len(life),
            "liq": t.reason == "liquidation",
            "censored": censored,
        })

    print("\n  === Par bucket : σ̂ vécu (durée de vie) vs σ̂ d'apprentissage ===")
    for b in range(3):
        sel = [r for r in rows if r["bucket"] == b and not r["censored"]]
        n_pos = len(sel)
        k = sum(r["liq"] for r in sel)
        p_obs = k / n_pos if n_pos else float("nan")
        ratios = [r["sig_life"] / r["sig_tr"] for r in sel]
        print(f"  bucket {b}: n={n_pos:4d} k={k:4d} p̂={p_obs:.4f} "
              f"σ̂_life/σ̂_train méd={np.median(ratios):.3f} "
              f"(q25={np.percentile(ratios,25):.3f} q75={np.percentile(ratios,75):.3f})")

    print("\n  === Test décisif : p̂ vs P(σ̂_life, μ̂_life) ===")
    for b in range(3):
        sel = [r for r in rows if r["bucket"] == b and not r["censored"]]
        n_pos = len(sel)
        k = sum(r["liq"] for r in sel)
        p_obs = k / n_pos if n_pos else float("nan")
        N_SUB = 300
        step = max(1, n_pos // N_SUB)
        sub = sel[::step]
        p_life = np.mean([mc_p(r["mu_life"], max(r["sig_life"], 1e-6)) for r in sub])
        p_tr = np.mean([mc_p(r["mu_tr"], r["sig_tr"]) for r in sub])
        print(f"  bucket {b}: n={n_pos:4d} k={k:4d} p̂={p_obs:.4f} "
              f"P(σ̂_life,μ̂_life)={p_life:.4f}  P(σ̂_tr,μ̂_tr)={p_tr:.4f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", choices=["real", "gbm"], default="real")
    ap.add_argument("--seed", type=int, default=60)
    args = ap.parse_args()

    if args.data == "real":
        df, meta = load_with_provenance(str(REAL_PATH))
        closes = df["close"].to_numpy(dtype=float)
        bars = bars_from_frame(df)
        run_diag(closes, bars, f"REEL ({meta['source']}, {len(df)} barres)")
    else:
        df = generate_gbm_hourly_ohlc(n_hours=51_594, mu_hourly=0.0002,
                                      sigma_hourly=0.025,
                                      steps_per_hour=STEPS, seed=args.seed)
        closes = df["close"].to_numpy(dtype=float)
        bars = bars_from_frame(df)
        run_diag(closes, bars, f"CONTROLE GBM (seed {args.seed}, {len(df)} barres)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
