"""
moments.py — Estimation (μ, σ), intervalles de confiance (J5).
===============================================================================
RATTACHEMENT : M1–M3 (estimation pour H2/H3/H4), M4 (utilitaire de proportion).

  Estimation sur les rendements LOGARITHMIQUES du close, à l'échelle horaire
  (échelle de la simulation). Le rapport μ/σ² qui entre dans la formule H2 est
  INVARIANT par changement d'unité de temps (μ et σ se rééchelonnent pareil) :
  les valeurs quotidiennes s'obtiennent par μ_d = 24·μ_h, σ_d = √24·σ_h.

  CONVENTIONS (documentées — producteur §8) :
    M1  μ̂ = moyenne des rendements logs, σ̂ = écart-type (ddof=1) → estimateurs
        non biaisés sous iid.
    M2  IC de μ̂ : Student t (hypothèse iid), t_{α/2, n−1}·σ̂/√n.
    M3  IC de σ̂ : χ² sur la variance (n−1)·s²/χ²_{α/2} … (n−1)·s²/χ²_{1−α/2},
        racine carrée.
    M4  IC de Wilson (proportion binomiale) : intervalle centré de façon
        non-symétrique, valable aussi pour k=0 et k=n. ATTENTION : H4 n'utilise
        PAS ce CI (les positions d'une fenêtre ne sont pas indépendantes) — le
        test H4 est le Wald cluster-robuste de thesis.py (V5). Wilson reste
        disponible comme utilitaire.
  ASSUME : rendements iid pour les IC (réfutable par autocorrélation — voir
  LIMITATIONS.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd
from scipy import stats


def log_returns(close: np.ndarray) -> np.ndarray:
    """M1 : rendements logs d'une série de closes (len = n−1)."""
    close = np.asarray(close, dtype=float)
    if close.ndim != 1 or close.size < 2:
        raise ValueError("close doit être un vecteur 1D d'au moins 2 valeurs.")
    if np.any(close <= 0):
        raise ValueError("close doit être strictement positif.")
    return np.log(close[1:] / close[:-1])


@dataclass(frozen=True)
class MomentEstimate:
    n: int
    mu: float                 # dérive horaire estimée
    sigma: float              # vol horaire estimée (ddof=1)
    mu_ci: Tuple[float, float]
    sigma_ci: Tuple[float, float]


def estimate_moments(close: np.ndarray, alpha_ci: float = 0.05) -> MomentEstimate:
    """M1–M3 : μ̂, σ̂ et leurs IC à niveau 1−α_ci."""
    if not (0.0 < alpha_ci < 1.0):
        raise ValueError(f"alpha_ci doit être dans (0, 1) : {alpha_ci}")
    r = log_returns(close)
    n = len(r)
    mu = float(r.mean())
    sigma = float(r.std(ddof=1))

    t = stats.t.ppf(1.0 - alpha_ci / 2.0, df=n - 1)
    se = sigma / np.sqrt(n)
    mu_ci = (mu - t * se, mu + t * se)

    chi2_lo = stats.chi2.ppf(alpha_ci / 2.0, df=n - 1)
    chi2_hi = stats.chi2.ppf(1.0 - alpha_ci / 2.0, df=n - 1)
    var_lo = (n - 1) * sigma ** 2 / chi2_hi
    var_hi = (n - 1) * sigma ** 2 / chi2_lo
    sigma_ci = (float(np.sqrt(var_lo)), float(np.sqrt(var_hi)))

    return MomentEstimate(n=n, mu=mu, sigma=sigma, mu_ci=mu_ci, sigma_ci=sigma_ci)


def rolling_moments(close: np.ndarray, window: int) -> pd.DataFrame:
    """μ̂_h et σ̂_h glissants (fenêtre fermée) pour la validation par fenêtres (H4)."""
    s = pd.Series(close)
    r = np.log(s / s.shift(1)).dropna()
    out = pd.DataFrame({
        "mu": r.rolling(window).mean(),
        "sigma": r.rolling(window).std(ddof=1),
    }).dropna()
    return out


def wilson_ci(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """M4 : intervalle de Wilson à (1−α)% pour une fréquence k/n (α via z)."""
    if n <= 0:
        raise ValueError("n doit être > 0.")
    if not (0 <= k <= n):
        raise ValueError(f"k hors borne : {k} not in [0, {n}].")
    if z <= 0:
        raise ValueError("z doit être > 0.")

    p = k / n
    denom = 1 + z ** 2 / n
    centre = p + z ** 2 / (2 * n)
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2))
    lo = (centre - half) / denom
    hi = (centre + half) / denom
    return (float(lo), float(hi))
