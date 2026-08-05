#!/usr/bin/env python3
"""
03_ground_truth.py — Vérité terrain GBM pour H2.
===============================================================================
RATTACHEMENT : H2 (ancre anti-contradiction).

  Monte Carlo de N trajectoires browniennes arithmétiques entre les barrières
  TP (−a) et liq (+b). Compare la fréquence observée p̂ à P(liq) prédite (H2)
  avec la tolérance binomiale 5σ. Sortie PASS / FAIL.

  Usage : python scripts/03_ground_truth.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.risk.monte_carlo import simulate_two_barrier
from src.risk.two_barriers import prob_liquidation_from_L


def main() -> int:
    L, s, mu, sigma = 5.0, 0.02, 0.0005, 0.03
    n, dt, cap, seed = 10_000, 0.01, 200_000, 42

    d = (1.0 / L - 0.005) / 1.005
    a, b = -math.log(1.0 - s), math.log(1.0 + d)

    gt = simulate_two_barrier(mu=mu, sigma=sigma, a=a, b=b, n=n, dt=dt, cap=cap, seed=seed)
    p_formule = prob_liquidation_from_L(L, s, mu, sigma)

    print(f"Paramètres : L={L}, s={s}, μ={mu}, σ={sigma}")
    print(f"Barrières  : a (TP) = {a:.5f}, b (liq) = {b:.5f}")
    print(f"N          : {gt.n} trajectoires (dt={dt}h, cap={cap})")
    print(f"Observé    : p̂(liq) = {gt.p_hat:.5f} ({gt.n_liquidated}/{gt.n})")
    print(f"Prédit H2  : P(liq) = {p_formule:.5f}")
    print(f"Tolérance  : 5σ = {gt.max_error_5sigma:.5f}")
    print(f"Indécises  : {gt.n_undecided}")

    ok = gt.passes() and abs(p_formule - gt.p_pred) < 1e-15
    print(f"\nRÉSULTAT : {'PASS' if ok else 'FAIL'} "
          f"(|p̂−P| = {abs(gt.p_hat - p_formule):.5f})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
