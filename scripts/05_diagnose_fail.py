#!/usr/bin/env python3
"""
05_diagnose_fail.py — Diagnostic du FAIL H4 (bucket vol 1) sur données réelles.
===============================================================================
RATTACHEMENT : H4. NE MODIFIE PAS le contrat H1–H5 : ce script ré-exécute le
protocole V1–V7 (`validate_thesis`) et décompose le FAIL par fenêtre et par
bucket, avec des statistiques de DIAGNOSTIC (non utilisées pour trancher la
thèse) :

  D1  Pour chaque fenêtre de test : σ̂_train (utilisé pour prédire), σ̂_test
      réalisé SUR la fenêtre de test, μ̂_train, μ̂_test, n, k, p̂_w, P̂_w.
      → sépare "non-stationnarité des paramètres" (σ̂_test ≠ σ̂_train) de
      "inadéquation structurelle du modèle".
  D2  Re-prédiction de contrôle : P̂ re-calculé avec les MOMENTS RÉALISÉS de la
      fenêtre de test (σ̂_test, μ̂_test). Si p̂_w ≈ P̂_test, le modèle de passage
      est sain et c'est l'écart train/test qui explique le FAIL ; si p̂_w reste
      très éloigné de P̂_test, la structure de chemin réelle (queues, mémoire)
      est en cause.
  D3  Statistiques de chemin : kurtosis des rendements horaires réels,
      autocorrélation lag-1, et part des liquidations dont la barre a une
      extension (high−close)/close extrême.
  D4  Répartition temporelle : quelles fenêtres réelles composent le bucket 1,
      avec leur période calendaire.

Usage :
  python scripts/05_diagnose_fail.py [--seed S] [--n-train T] [--n-test T]
  (paramètres de grille L/s identiques à 04 ; pas d'écriture de résultat
  ailleurs que la sortie console.)

Sortie : console uniquement — documentée dans docs/ENQUETE_FAIL.md.
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from pathlib import Path

import numpy as np
from scipy import stats as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.data_loader import load_with_provenance
from src.risk.moments import estimate_moments, log_returns
from src.risk.monte_carlo import simulate_two_barrier_bars
from src.simulator.engine import bars_from_frame
from src.simulator.runner import RunConfig, run_backtest
from src.strategy.grid_short import GridConfig, ShortGridStrategy
from src.validation.thesis import validate_thesis, predict_discrete, _bucket_id
from src.validation.windows import build_windows, tag_opening_indices

REAL_PATH = Path("data/raw/SOLUSDT_1h.csv")


def mc_p(mu: float, sigma: float, L: float, s: float, mmr: float = 0.0050,
         steps: int = 30, n_paths: int = 20_000, seed: int = 0) -> float:
    d = (1.0 / L - mmr) / (1.0 + mmr)
    a = -np.log(1.0 - s)
    b = np.log(1.0 + d)
    gt = simulate_two_barrier_bars(mu, sigma, a, b, n=n_paths,
                                   steps_per_hour=steps, seed=seed)
    return gt.p_hat


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=60)
    ap.add_argument("--n-train", type=int, default=2000)
    ap.add_argument("--n-test", type=int, default=1000)
    ap.add_argument("--L", type=float, default=5.0)
    ap.add_argument("--s", type=float, default=0.02)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--mc-paths", type=int, default=20_000)
    args = ap.parse_args()

    df, meta = load_with_provenance(str(REAL_PATH))
    closes = df["close"].to_numpy(dtype=float)
    bars = bars_from_frame(df)
    print(f"Données réelles : {meta['source']} — {len(df)} barres 1h")

    windows = build_windows(len(bars), args.n_train, args.n_test)
    print(f"Fenêtres : {len(windows)} (train={args.n_train}, test={args.n_test})")

    grid_cfg = GridConfig(grid_size=1, grid_ratio=args.s, qty_sol=10.0,
                          leverage=args.L)
    run_cfg = RunConfig(initial_capital=10_000.0)

    res = run_backtest(list(bars), ShortGridStrategy(grid_cfg), cfg=run_cfg)
    engine = res.engine

    ts_to_idx = {bar.ts: i for i, bar in enumerate(bars)}
    opening = [ts_to_idx[t.opened_at] for t in engine.trades]
    win_of = tag_opening_indices(opening, windows)
    wid_set = {w.id for w in windows}

    n_by_win = {w.id: 0 for w in windows}
    k_by_win = {w.id: 0 for w in windows}
    for i, t in enumerate(engine.trades):
        w = win_of[i]
        if w in wid_set:
            n_by_win[w] += 1
            if t.reason == "liquidation":
                k_by_win[w] += 1

    rows = []
    for w in windows:
        em = estimate_moments(closes[w.train_start:w.train_end])
        em_test = estimate_moments(closes[w.test_start:w.test_end])
        p_train = mc_p(em.mu, em.sigma, args.L, args.s, steps=args.steps,
                       n_paths=args.mc_paths, seed=0)
        p_test = mc_p(em_test.mu, em_test.sigma, args.L, args.s,
                      steps=args.steps, n_paths=args.mc_paths, seed=0)
        n = n_by_win[w.id]
        k = k_by_win[w.id]
        rows.append({
            "id": w.id,
            "mu_tr": em.mu, "sig_tr": em.sigma,
            "mu_te": em_test.mu, "sig_te": em_test.sigma,
            "n": n, "k": k,
            "p_obs": k / n if n else float("nan"),
            "p_pred_train": p_train,
            "p_pred_test": p_test,
            "t0": df.index[w.test_start],
            "t1": df.index[w.test_end - 1],
        })

    sig_tr = np.array([r["sig_tr"] for r in rows])
    thr = np.quantile(sig_tr, [1 / 3, 2 / 3])
    print(f"Seuils terciles σ̂_train : {thr[0]:.5f} / {thr[1]:.5f}")

    print("\n=== Fenêtres par bucket (vol d'apprentissage) ===")
    print(f"{'bkt':>3} {'win':>3} {'sig_tr':>7} {'sig_te':>7} "
          f"{'mu_tr':>9} {'mu_te':>9} {'n':>4} {'k':>3} "
          f"{'p_obs':>6} {'P_tr':>6} {'P_te':>6}  fenêtre")
    for b in range(3):
        sel = [r for r in rows if _bucket_id(r["sig_tr"], thr) == b]
        agg_n = sum(r["n"] for r in sel)
        agg_k = sum(r["k"] for r in sel)
        print(f"-- bucket {b} : {len(sel)} fenêtres, n={agg_n}, k={agg_k}, "
              f"p̂={agg_k / agg_n:.4f}" if agg_n else f"-- bucket {b} : vide")
        for r in sorted(sel, key=lambda r: r["sig_tr"]):
            print(f"{b:>3} {r['id']:>3} {r['sig_tr']:7.5f} {r['sig_te']:7.5f} "
                  f"{r['mu_tr']:9.2e} {r['mu_te']:9.2e} {r['n']:>4} {r['k']:>3} "
                  f"{r['p_obs']:6.4f} {r['p_pred_train']:6.4f} "
                  f"{r['p_pred_test']:6.4f}  {r['t0'].strftime('%Y-%m')}→"
                  f"{r['t1'].strftime('%Y-%m')}")

    # D1 : ratio σ_test/σ_train par bucket
    print("\n=== D1 : σ̂_test réalisé vs σ̂_train (ratio) ===")
    for b in range(3):
        sel = [r for r in rows if _bucket_id(r["sig_tr"], thr) == b]
        ratios = [r["sig_te"] / r["sig_tr"] for r in sel]
        print(f"  bucket {b}: {len(ratios)} fenêtres, ratio médian "
              f"{np.median(ratios):.3f}, min {np.min(ratios):.3f}, "
              f"max {np.max(ratios):.3f}")

    # D2 : modèle de passage re-calibré sur moments réalisés
    print("\n=== D2 : re-prédiction sur moments réalisés (contrôle) ===")
    for b in range(3):
        sel = [r for r in rows if _bucket_id(r["sig_tr"], thr) == b and r["n"]]
        n = sum(r["n"] for r in sel)
        k = sum(r["k"] for r in sel)
        p_obs = k / n
        p_tr = sum(r["n"] * r["p_pred_train"] for r in sel) / n
        p_te = sum(r["n"] * r["p_pred_test"] for r in sel) / n
        print(f"  bucket {b}: n={n:5d} k={k:4d} p̂={p_obs:.4f} "
              f"P(train)={p_tr:.4f} P(test)={p_te:.4f}")

    # D3 : statistiques de chemin réelles
    print("\n=== D3 : structure de chemin réelle (1h) ===")
    r_all = log_returns(closes)
    print(f"  kurtosis excès : {st.kurtosis(r_all):.2f}")
    print(f"  skewness      : {st.skew(r_all):.2f}")
    ac1 = np.corrcoef(r_all[:-1], r_all[1:])[0, 1]
    print(f"  autocorr lag-1 : {ac1:.4f}")
    q = np.quantile(np.abs(r_all), 0.999)
    print(f"  |r| p99.9 : {q:.5f} (= {q / r_all.std(ddof=1):.1f} σ)")

    # D4 : causes directes des liquidations — barres de liq
    liq_bars = []
    for t in engine.trades:
        if t.reason == "liquidation":
            liq_bars.append(t)
    print(f"\n  liquidations totales : {len(liq_bars)}")
    big = [t for t in liq_bars if t.gross_pnl <= -500]
    print(f"  liq avec perte brute ≥ 500 USD (1/2 marge à qty=10) : {len(big)}")

    # diagnostic du résidu du bucket 1 : contribution par fenêtre
    print("\n=== Résidu (p̂_w − P̂_w) par fenêtre du bucket 1 ===")
    sel = [r for r in rows if _bucket_id(r["sig_tr"], thr) == 1 and r["n"]]
    for r in sorted(sel, key=lambda r: r["id"]):
        resid = r["p_obs"] - r["p_pred_train"]
        print(f"  win {r['id']:>3} n={r['n']:>4} k={r['k']:>3} "
              f"p̂={r['p_obs']:.4f} P={r['p_pred_train']:.4f} "
              f"résidu={resid:+.4f} sig_te/sig_tr={r['sig_te'] / r['sig_tr']:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
