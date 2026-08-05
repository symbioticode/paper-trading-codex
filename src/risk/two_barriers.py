"""
two_barriers.py — Probabilité de liquidation (H2) et plafond de levier (H3).
===============================================================================
RATTACHEMENT : H2 (formule exacte), H3 (plafond L*).

  Modèle : log-prix en mouvement brownien arithmétique X_t = X_0 + μt + σW_t.
  Un SHORT entre à E. Le prix de liquidation (barrière HAUTE) est
      liq = E·(1+d),  d = (1/L − MMR)/(1+MMR)        (H1)
  et le take-profit (barrière BASSE) est
      TP = E·(1−s),   s = espacement de grille.
  Distances logarithmiques exactes :
      a = ln(E/TP) = −ln(1−s)   (vers le TP)
      b = ln(liq/E) = ln(1+d)   (vers la liquidation)
  P(liq) = P(hit +b avant −a | départ 0), forme fermée du premier passage à
  deux barrières (H2) :
      P(liq) = (1 − e^{2μa/σ²}) / (e^{−2μb/σ²} − e^{2μa/σ²})
      = expm1(−2μa/σ²) / expm1(−2μ(a+b)/σ²)     (forme numériquement stable)

  CONVENTIONS (documentées — producteur §8) :
    T1  μ, σ sont dans la MÊME unité de temps (heures ici) ; P(liq) ne dépend
        que du rapport μ/σ², invariant par changement d'unité.
    T2  Domaine valide : a > 0 (s > 0), b > 0 (1/L > MMR ⟺ L < 1/MMR).
        Hors domaine → ValueError explicite.
    T3  Cas limites exacts : μ→0 ⇒ P = a/(a+b) ; b→0 ⇒ P→1 ; a→0 ⇒ P→0.
    T4  L* = max{L : P(liq)(L) ≤ α} résolu par dichotomie (P monotone
        croissante en L dans le domaine valide — vérifié par le test H3).
    T5  L* = None si α < P(liq)(L→1⁺) : aucun levier ne respecte le budget.
"""

from __future__ import annotations

import math
from typing import Optional


def _prob_from_ab(a: float, b: float, mu: float, sigma: float) -> float:
    if sigma <= 0.0:
        raise ValueError(f"sigma doit être > 0 : {sigma}")
    if a <= 0.0 or b <= 0.0:
        raise ValueError(f"barrières strictement positives requises : a={a}, b={b}")

    if mu == 0.0:
        return a / (a + b)

    X = 2.0 * mu * a / sigma ** 2
    Y = 2.0 * mu * b / sigma ** 2
    if mu > 0.0:
        # args d'expm1 négatifs → pas de dépassement ; μ→0⁺ ⇒ P→a/(a+b)
        return math.expm1(-X) / math.expm1(-(X + Y))
    # μ < 0 : forme e^{Y}·expm1(X)/expm1(X+Y), tous les termes bornés ;
    # μ→0⁻ ⇒ expm1(X)/expm1(X+Y)→X/(X+Y)=a/(a+b)
    return math.exp(Y) * math.expm1(X) / math.expm1(X + Y)


def prob_liquidation_short(
    entry: float,
    tp_price: float,
    liq_price: float,
    mu: float,
    sigma: float,
) -> float:
    """H2 : P(liq) d'un SHORT entre son TP (E·(1−s)) et sa liq (E·(1+d))."""
    if entry <= 0 or tp_price <= 0 or liq_price <= entry:
        raise ValueError(
            f"Géométrie invalide : entry={entry}, tp={tp_price}, liq={liq_price} "
            "(liq doit être > entry pour un SHORT)."
        )
    a = math.log(entry / tp_price)
    b = math.log(liq_price / entry)
    return _prob_from_ab(a, b, mu, sigma)


def prob_liquidation_from_L(
    leverage: float,
    s: float,
    mu: float,
    sigma: float,
    mmr: float = 0.0050,
) -> float:
    """H2 exprimée en levier : calcule la liq via H1 puis P(liq)."""
    if leverage >= 1.0 / mmr:
        raise ValueError(
            f"1/L < MMR : levier {leverage} ≥ 1/MMR = {1.0 / mmr:.4f} → position "
            "impossible (liq = entry, H1)."
        )
    d = (1.0 / leverage - mmr) / (1.0 + mmr)
    entry = 1.0
    tp = entry * (1.0 - s)
    liq = entry * (1.0 + d)
    return prob_liquidation_short(entry, tp, liq, mu, sigma)


def max_leverage_for_alpha(
    alpha: float,
    s: float,
    mu: float,
    sigma: float,
    mmr: float = 0.0050,
    tol: float = 1e-12,
    max_iter: int = 80,
) -> Optional[float]:
    """H3 : L* = max{L : P(liq)(L) ≤ α}, résolu par dichotomie (T4).

    Retourne None si aucun levier ne satisfait le budget (T5).
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha doit être dans (0, 1) : {alpha}")
    if s <= 0.0 or s >= 1.0:
        raise ValueError(f"s doit être dans (0, 1) : {s}")
    if sigma <= 0.0:
        raise ValueError(f"sigma doit être > 0 : {sigma}")

    lo = 1.0 + tol                       # L → 1⁺
    hi = 1.0 / mmr - tol                 # L < 1/MMR (T2)

    def P(L: float) -> float:
        return prob_liquidation_from_L(L, s, mu, sigma, mmr)

    if P(lo) > alpha:
        return None                      # T5 : même au levier minimal, budget dépassé

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if P(mid) <= alpha:
            lo = mid
        else:
            hi = mid
    return lo
