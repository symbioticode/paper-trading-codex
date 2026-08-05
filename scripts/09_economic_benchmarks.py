#!/usr/bin/env python3
"""
09_economic_benchmarks.py — Constat économique et benchmarks (REV03 §4).
========================================================================
RATTACHEMENT : REV03 §4 « séparation risque / rentabilité ». Ce script produit
le constat économique du portefeuille grid SHORT — une MESURE, séparée de la
thèse de liquidation (H1–H6). Il ne teste aucune hypothèse falsifiable : il
documente ce qui s'est passé sur la fenêtre mesurée.

  Le couple (L=5, s=2 %) est le constat PUBLIÉ, choisi par le porteur du
  projet (pas par une procédure publiée — LIMITATIONS §2.4). La sensibilité
  L/s/frais/slippage est une couche EXPLORATOIRE : elle est exécutée sur les
  mêmes données mais n'a qu'un rôle de contexte, jamais de sélection — aucun
  (L,s) n'est « retenu » ici, le constat publié reste figé.

    Usage :
      python scripts/05_economic_benchmarks.py [--data real|gbm] [--capital USD]
                                                [--L L] [--s s]
                                                [--fees scale] [--slip bps]

  Sorties :
    1. Constat publié (L=5, s=2 %) : espérance par trade décomposée
       (TP / liquidations / frais / funding), taux de liq réalisé, equity,
       drawdown max, utilisation cash, exposition simultanée, positions
       ouvertes en fin de jeu.
    2. Taux de liquidation d'équilibre (calcul explicite, référence).
    3. Benchmarks sur le même historique : Buy & Hold, cash pur, grille SHORT
       sans levier (L≈1).
    4. Sensibilité exploratoire (L, s, frais, slippage) — marquée EXPLORATION,
       jamais publiée comme résultat.
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
from src.simulator.engine import bars_from_frame
from src.simulator.runner import RunConfig, run_backtest
from src.strategy.grid_short import GridConfig, ShortGridStrategy

REAL_PATH = Path("data/raw/SOLUSDT_1h.csv")


def run_constat(bars, capital: float, L: float, s: float, fee_scale: float,
                slip_bps: float, qty: float = 10.0) -> object:
    """Lance la grille SHORT et renvoie le RunResult + le résumé économique."""
    grid_cfg = GridConfig(grid_size=1, grid_ratio=s, qty_sol=qty, leverage=L)
    run_cfg = RunConfig(
        initial_capital=capital,
        maker_fee=0.0002 * fee_scale,
        taker_fee=0.0004 * fee_scale,
        slip_bps=slip_bps,
    )
    res = run_backtest(bars, ShortGridStrategy(grid_cfg), cfg=run_cfg)
    return res


def max_simultaneous_exposure(engine) -> float:
    """Exposition simultanée maximale = max sur le temps de Σ notionnels
    (entry·qty) des positions ouvertes, reconstruit depuis opened_at/closed_at.
    """
    events = []  # (ts, delta_notional)
    for t in engine.trades:
        events.append((t.opened_at, t.entry * t.qty))
        events.append((t.closed_at, -t.entry * t.qty))
    for p in engine.positions:
        events.append((p.opened_at, p.notional))
    events.sort(key=lambda e: e[0])
    cur = 0.0
    peak = 0.0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    return peak


def summarize(engine, capital: float, label: str) -> None:
    """Résumé économique chiffré d'un run (constat ou benchmark)."""
    trades = engine.trades
    tp = [t for t in trades if t.reason == "take_profit"]
    liq = [t for t in trades if t.reason == "liquidation"]

    gross = sum(t.gross_pnl for t in trades)
    entry_fees = sum(t.entry_fee for t in trades)
    exit_fees = sum(t.exit_fee for t in trades)
    funding = sum(t.funding for t in trades)
    net = sum(t.net_pnl for t in trades)

    resolved = len(tp) + len(liq)
    liq_rate = (len(liq) / resolved) if resolved else float("nan")

    realized_equity = engine.equity_usd()          # cash + marges (publié)
    marked_equity = (engine.history[-1].equity_usd if engine.history
                     else engine.equity_usd())     # + PnL non réalisé (mark)
    peak = -float("inf")
    max_dd = 0.0
    min_cash_ratio = 1.0
    max_pos = 0
    for st in engine.history:
        peak = max(peak, st.equity_usd)
        if peak > 0:
            max_dd = max(max_dd, (peak - st.equity_usd) / peak)
        min_cash_ratio = min(min_cash_ratio, st.cash_usd / capital)
        max_pos = max(max_pos, st.n_positions)

    max_expo = max_simultaneous_exposure(engine)

    print(f"=== {label} ===")
    print(f"  trades fermés : {len(trades)}  (TP {len(tp)} / liq {len(liq)})"
          f"  positions ouvertes en fin : {len(engine.positions)}")
    print(f"  taux de liq réalisé (résolus) : {liq_rate:.4f}")
    print(f"  PnL net total : {net:,.2f} USD")
    print(f"    brut  : {gross:,.2f}   frais entrée : {entry_fees:,.2f}   "
          f"frais sortie : {exit_fees:,.2f}   funding : {funding:,.2f}")
    if trades:
        print(f"    PnL net par trade fermé : {net / len(trades):,.2f} USD")
    if tp:
        net_tp = sum(t.net_pnl for t in tp)
        fees_tp = sum(t.entry_fee + t.exit_fee for t in tp)
        print(f"    TP ({len(tp)}) : net {net_tp:,.2f} USD "
              f"({net_tp/len(tp):,.2f}/trade, frais {fees_tp:,.2f})")
    if liq:
        net_liq = sum(t.net_pnl for t in liq)
        fees_liq = sum(t.entry_fee for t in liq)
        print(f"    LIQ ({len(liq)}) : net {net_liq:,.2f} USD "
              f"({net_liq/len(liq):,.2f}/trade, frais {fees_liq:,.2f})")
    print(f"  equity finale réalisée : {realized_equity:,.2f} USD "
          f"({100*(realized_equity/capital - 1):+.2f} %)  "
          f"marquée : {marked_equity:,.2f} USD "
          f"({100*(marked_equity/capital - 1):+.2f} %)")
    print(f"  drawdown max : {100*max_dd:.2f} %   cash min (fraction du capital) : "
          f"{min_cash_ratio:.2f}   max positions simultanées : {max_pos}"
          f"   exposition max : {max_expo:,.0f} USD")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", choices=["gbm", "real"], default="real")
    ap.add_argument("--capital", type=float, default=10_000.0)
    ap.add_argument("--L", type=float, default=5.0)
    ap.add_argument("--s", type=float, default=0.02)
    ap.add_argument("--fee-scale", type=float, default=1.0)
    ap.add_argument("--slip", type=float, default=0.0)
    ap.add_argument("--n-hours", type=int, default=30_000)
    ap.add_argument("--seed", type=int, default=60)
    args = ap.parse_args()

    if args.data == "real":
        df, meta = load_with_provenance(str(REAL_PATH))
        print(f"Données réelles : {meta['source']} — {len(df)} barres 1h "
              f"SOLUSDT perp (sha256 {meta['sha256'][:16]}…)")
    else:
        df = generate_gbm_hourly_ohlc(
            n_hours=args.n_hours, mu_hourly=0.0002, sigma_hourly=0.025,
            steps_per_hour=30, seed=args.seed,
        )
        print(f"Contrôle GBM synthétique (seed={args.seed}) : {len(df)} barres")
    closes = df["close"].to_numpy(dtype=float)
    bars = bars_from_frame(df)
    print(f"Période : {df.index[0]} → {df.index[-1]}  "
          f"rendement sous-jacent {100*(closes[-1]/closes[0]-1):+.2f} %\n")

    # ── 1. Constat publié ──────────────────────────────────────────────────
    res = run_constat(bars, args.capital, args.L, args.s, 1.0, 0.0)
    summarize(res.engine, args.capital,
              f"CONSTAT PUBLIÉ — grille SHORT L={args.L:g}, s={100*args.s:.0f} %, "
              f"frais 1×, slip 0")

    # ── 2. Taux de liquidation d'équilibre (trois conventions, REV03-1 §3) ─
    def _thr(label: str, g_tp: float, l_liq: float) -> None:
        q = g_tp / (g_tp + abs(l_liq))
        print(f"  {label:<34}{q:.4f}")

    N = 1.0
    g_coarse = args.s * N
    l_coarse = N / args.L
    g_engine = args.s * N - N * 0.0002 - (1 - args.s) * N * 0.0004
    l_engine = N / args.L + N * 0.0002
    d_h1 = (1 / args.L - 0.005) / (1 + 0.005)
    print("=== Taux de liquidation d'équilibre — trois conventions (REV03-1 §3) ===")
    print("  formules générales : q* = G_TP / (G_TP + |L_liq|) ; "
          "aucun seuil publié sans convention (docs/ECONOMICS.md §2)")
    _thr("grossier (aucun coût) :", g_coarse, l_coarse)
    _thr("moteur (frais par défaut, E5/E11) :", g_engine, l_engine)
    _thr(f"géométrie H1 (d={100*d_h1:.2f} %) :", args.s * N, d_h1 * N)
    print()

    # ── 3. Benchmarks passifs (même historique, même capital) ──────────────
    bh = args.capital * (closes[-1] / closes[0] - 1.0)
    print("=== Benchmarks passifs (même capital, même période) ===")
    print(f"  Buy & Hold (long, entrée au premier close) : "
          f"{100*(closes[-1]/closes[0]-1):+.2f} %  →  {args.capital + bh:,.2f} USD")
    print(f"  Cash pur (0 % de rendement)                :  0.00 %  →  "
          f"{args.capital:,.2f} USD")
    # « Sans levier » = même risque de capital PAR POSITION que le constat :
    # on réduit qty pour que marge = notionnel/L reste identique à L=5/qty=10.
    # À L≈1, liq ~ +98 % (quasi jamais) : le TP gagne alors s·(notionnel réduit).
    L_UNLEV = 1.01
    qty_unlev = 10.0 * L_UNLEV / args.L
    unlevered = run_constat(bars, args.capital, L_UNLEV, args.s, 1.0, 0.0,
                            qty=qty_unlev)
    summarize(unlevered.engine, args.capital,
              "BENCHMARK — grille SHORT SANS LEVIER (L≈1.01, liq ~ +98 %, "
              f"qty {qty_unlev:.2f} SOL : marge/position identique au constat)")

    # ── 4. Sensibilité EXPLORATOIRE (jamais une sélection) ─────────────────
    print("=== SENSIBILITÉ EXPLORATOIRE (contexte uniquement — aucun (L,s) ")
    print("    n'est retenu ici ; le constat publié reste L=5, s=2 %) ===")
    print(f"  {'param':<22}{'trades':>7}{'PnL net':>14}{'equity fin':>14}"
          f"{'liq_rate':>10}{'dd max':>9}")

    def sens_row(key: str, L: float, s: float, fee_scale: float,
                 slip: float) -> None:
        r = run_constat(bars, args.capital, L, s, fee_scale, slip)
        eq = r.engine.history[-1].equity_usd
        tp = [t for t in r.engine.trades if t.reason == "take_profit"]
        liq = [t for t in r.engine.trades if t.reason == "liquidation"]
        net = sum(t.net_pnl for t in r.engine.trades)
        peak = -float("inf")
        dd = 0.0
        for st in r.engine.history:
            peak = max(peak, st.equity_usd)
            dd = max(dd, (peak - st.equity_usd) / peak)
        lr = len(liq) / (len(tp) + len(liq)) if tp or liq else float("nan")
        print(f"  {key:<22}{len(r.engine.trades):>7}{net:>14,.2f}"
              f"{eq:>14,.2f}{lr:>10.4f}{100*dd:>9.2f}")

    for L in (3.0, 8.0):
        sens_row(f"L={L:g}", L, args.s, 1.0, 0.0)
    for s in (0.01, 0.03):
        sens_row(f"s={s:g}", args.L, s, 1.0, 0.0)
    for scale in (0.5, 2.0):
        sens_row(f"fees×{scale:g}", args.L, args.s, scale, 0.0)
    for slip in (10.0, 30.0):
        sens_row(f"slip={slip:g}bps", args.L, args.s, 1.0, slip)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
