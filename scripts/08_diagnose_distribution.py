#!/usr/bin/env python3
"""
08_diagnose_distribution.py — P(liq) : barres gaussiennes vs barres EMPIRIQUES réelles.
===============================================================================
RATTACHEMENT : H4. Diagnostic SEUL (ne modifie pas le contrat H1–H5).

  Question (structure) : à (μ, σ) IDENTIQUES, le passage à deux barrières avec
  des barres réelles (queues épaisses, skew, auto-corr) donne-t-il une P(liq)
  différente de celle des barres gaussiennes du modèle ?

  Pour un SHORT : liq à +b (barrière LOINTAINE, +19.4%), TP à −a (barrière
  PROCHE, −2%). Des queues épaisses dans les deux sens : un grand saut BAS
  absorbe la position au TP (−2% se franchit facilement avec |r| jusqu'à 7σ),
  avant qu'elle ne puisse dériver vers +19.4%. Si c'est le cas, P_emp < P_gauss :
  la structure réelle SUFFIT à sous-prédire les liquidations.

  MÉTHODE : MC identique à simulate_two_barrier_bars, mais les rendements
  delta de barre sont tirés de l'HISTOGRAMME EMPIRIQUE des rendements réels
  (rééchelonnés à la même σ, échantillonnage avec remise + blocs pour
  préserver l'auto-corrélation). Bridge intra-barre inchangé (pont standard).

Usage :
  python scripts/08_diagnose_distribution.py [--sigma X] [--mu X] [--seed S]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.data_loader import load_with_provenance
from src.risk.moments import log_returns

REAL_PATH = Path("data/raw/SOLUSDT_1h.csv")
L, S, MMR = 5.0, 0.02, 0.0050
STEPS = 30
N = 20_000


def barriers():
    d = (1.0 / L - MMR) / (1.0 + MMR)
    a = -np.log(1.0 - S)
    b = np.log(1.0 + d)
    return a, b


def mc_with_delta_rng(draw_delta, mu: float, sigma: float, a: float, b: float,
                      n: int, m: int, cap: int, seed: int) -> float:
    """MC identique à simulate_two_barrier_bars, delta tiré par `draw_delta`."""
    rng = np.random.default_rng(seed)
    X = np.zeros(n, dtype=float)
    done = np.zeros(n, dtype=bool)
    result = np.zeros(n, dtype=np.int8)
    for _ in range(cap):
        active = ~done
        cnt = int(active.sum())
        if cnt == 0:
            break
        delta = draw_delta(rng, cnt)
        u = rng.normal(0.0, 1.0 / np.sqrt(m), (cnt, m))
        U = np.cumsum(u, axis=1)
        bridge = U - (np.arange(1, m + 1) / m)[None, :] * U[:, -1:]
        logpath = (delta[:, None] * (np.arange(1, m + 1) / m)[None, :]) + sigma * bridge
        bar_max = logpath.max(axis=1)
        bar_min = logpath.min(axis=1)
        idx = np.nonzero(active)[0]
        Xa = X[idx]
        liq = Xa + bar_max >= b
        tp = ~liq & (Xa + bar_min <= -a)
        result[idx[liq]] = 1
        result[idx[tp]] = 2
        done[idx[liq | tp]] = True
        X[idx[~liq & ~tp]] += delta[~liq & ~tp]
    return float((result == 1).sum()) / n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sigma", type=float, default=0.0127)
    ap.add_argument("--mu", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    df, meta = load_with_provenance(str(REAL_PATH))
    r_all = log_returns(df["close"].to_numpy(dtype=float))
    sigma_real = r_all.std(ddof=1)
    r_std = (r_all - r_all.mean()) / sigma_real
    print(f"Réel : {meta['source']} — {len(r_all)} rendements, "
          f"σ={sigma_real:.5f}, kurt={__import__('scipy').stats.kurtosis(r_all):.1f}")

    a, b = barriers()
    print(f"Barrières : TP={-a:.4f} (−{S*100:.1f}%), liq=+{b:.4f} "
          f"(+{100*(np.exp(b)-1):.1f}%)")

    rng0 = np.random.default_rng(0)
    samples = r_std[1:]  # réservoir de rendements normalisés (iid i.d.)

    def draw_gauss(rng, cnt, mu=args.mu, sigma=args.sigma):
        return rng.normal(mu, sigma, cnt)

    def draw_emp(rng, cnt, mu=args.mu, sigma=args.sigma, reservoir=samples):
        # blocs de 24 pour préserver l'auto-corrélation, rééchelonné à la σ cible
        out = np.empty(cnt)
        filled = 0
        while filled < cnt:
            i = rng.integers(0, len(reservoir) - 24)
            block = reservoir[i:i + 24]
            take = min(24, cnt - filled)
            out[filled:filled + take] = block[:take]
            filled += take
        return mu + sigma * out

    print("\n=== P(liq) à (μ, σ) identiques : barres gaussiennes vs empiriques ===")
    print(f"{'σ':>8} {'μ':>9} {'P_gauss':>8} {'P_emp':>8}  Δ(P_emp−P_gauss)")
    for mu in (0.0, args.mu):
        for sigma in (args.sigma, sigma_real):
            p_g = mc_with_delta_rng(draw_gauss, mu, sigma, a, b, N, STEPS, 400, args.seed)
            p_e = mc_with_delta_rng(draw_emp, mu, sigma, a, b, N, STEPS, 400, args.seed)
            print(f"{sigma:8.5f} {mu:9.2e} {p_g:8.4f} {p_e:8.4f}  {p_e - p_g:+.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
