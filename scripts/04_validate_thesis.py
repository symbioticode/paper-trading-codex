#!/usr/bin/env python3
"""
04_validate_thesis.py — Validation H4 : fréquence de liquidation prédite vs observée.
===============================================================================
RATTACHEMENT : H4 (le cœur falsifiable du projet), V1–V7 (thesis.py).

  Jeu de contrôle (par défaut) : GBM OHLC horaire `generate_gbm_hourly_ohlc`
  (30 sous-pas/heure), où le modèle est VRAI par construction : H4 doit PASSER.
  Sur les données réelles, H4 est le test falsifiable de la thèse SHORT.

  Usage :
    python scripts/04_validate_thesis.py [--data real|gbm] [--seed S]
                                          [--n-train T] [--n-test T]
                                          [--L L] [--s s]
                                          [--steps N] [--mc-paths N]

  Sorties :
    - Résumé par bucket de volatilité (Wald cluster-robuste 95%) + global, PASS/FAIL ;
    - PnL net USD par fenêtre (constat, séparé de la thèse) ;
    - Le jeu réel : provenance sha256 et comptage des barres.
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.data_loader import load_with_provenance
from data.synthetic_gbm import generate_gbm_hourly_ohlc
from src.simulator.engine import bars_from_frame
from src.simulator.runner import RunConfig, run_backtest
from src.strategy.grid_short import GridConfig, ShortGridStrategy
from src.validation.thesis import predict_discrete, validate_thesis
from src.validation.windows import build_windows, tag_opening_indices

REAL_PATH = Path("data/raw/SOLUSDT_1h.csv")


def pnl_by_window(engine, bars, windows) -> None:
    """Constat PnL réalisé par fenêtre d'ouverture (HORS thèse : mesure)."""
    ts_to_idx = {bar.ts: i for i, bar in enumerate(bars)}
    opening = [ts_to_idx[t.opened_at] for t in engine.trades]
    win_of = tag_opening_indices(opening, windows)

    total = 0.0
    per: dict[int, float] = {}
    for i, t in enumerate(engine.trades):
        w = win_of[i]
        per[w] = per.get(w, 0.0) + t.net_pnl
        total += t.net_pnl

    print(f"    trades={len(engine.trades)}  PnL total réalisé={total:,.2f} USD")
    print(f"    equity_fin={engine.equity_usd():,.2f} USD "
          f"(capital initial 10 000)")
    print(f"    positions ouvertes en fin de jeu : {len(engine.positions)}")
    for w in sorted(per):
        tag = "hors fenêtre" if w == -1 else f"fenêtre {w}"
        print(f"      {tag:14s}: {per[w]:>12,.2f} USD")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", choices=["gbm", "real"], default="gbm")
    ap.add_argument("--seed", type=int, default=60)
    ap.add_argument("--n-train", type=int, default=2000)
    ap.add_argument("--n-test", type=int, default=1000)
    ap.add_argument("--L", type=float, default=5.0)
    ap.add_argument("--s", type=float, default=0.02)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--mc-paths", type=int, default=20_000)
    ap.add_argument("--n-hours", type=int, default=30_000)
    args = ap.parse_args()

    if args.data == "gbm":
        df = generate_gbm_hourly_ohlc(
            n_hours=args.n_hours, mu_hourly=0.0002, sigma_hourly=0.025,
            steps_per_hour=args.steps, seed=args.seed,
        )
        print(f"Contrôle GBM (synthetic, seed={args.seed}) : "
              f"{len(df)} barres 1h, steps/heure={args.steps}")
    else:
        df, meta = load_with_provenance(str(REAL_PATH))
        print(f"Données réelles : {meta['source']} — "
              f"{len(df)} barres 1h SOLUSDT perp")
        print(f"  provenance sha256 : {meta['sha256'][:16]}…")
        print(f"  ASSUME : granularité intra-barre = {args.steps} pas/heure "
              "pour la prédiction (modèle de pont)")

    closes = df["close"].to_numpy(dtype=float)
    bars = bars_from_frame(df)

    windows = build_windows(len(bars), args.n_train, args.n_test)
    print(f"Fenêtres : {len(windows)} (train={args.n_train}, test={args.n_test})")

    grid_cfg = GridConfig(
        grid_size=1, grid_ratio=args.s, qty_sol=10.0, leverage=args.L,
    )
    run_cfg = RunConfig(initial_capital=10_000.0)

    predictor = partial(
        predict_discrete, steps_per_hour=args.steps, n_paths=args.mc_paths, seed=0,
    )

    report = validate_thesis(
        closes, bars, windows, grid_cfg, run_cfg=run_cfg, predictor=predictor,
    )

    print("\n=== H4 : P(liq) prédite vs observée (Wald cluster-robuste 95%) ===")
    print(report.summary())
    print(f"  censurées : {report.n_censored}   skips (cash/cap) : {report.n_skipped}")

    print("\n=== Constat PnL (hors thèse, mesure uniquement) ===")
    res = run_backtest(bars, ShortGridStrategy(grid_cfg), cfg=run_cfg)
    pnl_by_window(res.engine, bars, windows)

    return 0 if report.passes else 1


if __name__ == "__main__":
    raise SystemExit(main())
