"""
synthetic_gbm.py — Contrôle GBM étiqueté, jamais présenté comme historique.
================================================================================
SPEC (rattachement : H2/H4 — fournir un *contrôle* dont la vérité est connue).

  RÔLE   : jeux de données synthétiques de contrôle, marqués "synthetic" dans
           la provenance. Utilisés uniquement pour :
             - tester la machinerie (pipeline, simulateur) hors réseau ;
             - valider H2 : sous GBM, la probabilité de liquidation prédite est
               vérifiable par Monte Carlo (vérité terrain analytique).
  NON   : jamais présenté comme performance historique.

  MODÈLE (ASSUME, déclaré — vérification cible : test d'adéquation statistique
  du pipeline, jamais comme modèle de marché réel) :
    - close_t = S0 · exp(cumsum(X_i)), X_i ~ N(mu_daily, sigma_daily) iid
      -> le rendement journalier du log-prix est gaussien (ASSUME).
    - open   = close préc. (pas de gap) ; high/low synthétisés comme
      close·(1 ± k·σ_intra) avec σ_intra paramétrable (ASSUME grossier :
      les excursions intraday réelles ont des queues plus lourdes).
  LIMITE DÉCLARÉE : le high/low synthétique n'est PAS fiable pour l'étude des
  liquidations intra-barre — pour H4, on utilise les données réelles 1h.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.data_loader import save_with_provenance


def generate_gbm_daily(
    start_price: float = 100.0,
    n_days: int = 365,
    mu_daily: float = -0.002,
    sigma_daily: float = 0.04,
    sigma_intra: float = 0.02,
    seed: int = 42,
) -> pd.DataFrame:
    """Génère une série journalière OHLCV GBM.

    INFER : rendements du log-prix tirés iid sous N(mu_daily, sigma_daily).
    OBSERVE : l'output est un DataFrame OHLCV canonique (déterministe pour un
    seed donné — reproductible par construction).
    """
    rng = np.random.default_rng(seed)

    log_returns = rng.normal(mu_daily, sigma_daily, n_days)
    close = start_price * np.exp(np.cumsum(log_returns))
    close = np.clip(close, 1e-8, None)

    open_ = np.roll(close, 1)
    open_[0] = start_price

    spread = np.abs(rng.normal(0.0, sigma_intra, n_days))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)

    volume = rng.uniform(1e6, 1e7, n_days)

    idx = pd.date_range("2020-01-01", periods=n_days, freq="D", tz="UTC")
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )
    df.index.name = "open_time"
    return df


def generate_gbm_hourly_ohlc(
    start_price: float = 100.0,
    n_hours: int = 30_000,
    mu_hourly: float = 0.0002,
    sigma_hourly: float = 0.025,
    steps_per_hour: int = 30,
    seed: int = 42,
) -> pd.DataFrame:
    """Génère des barres 1h OHLC d'un GBM SANS l'approximation point-barres.

    Le GBM est simulé à `steps_per_hour` sous-pas par heure puis AGRÉGÉ en
    barres horaires (open/high/low/close). Les extrêmes intra-heure du high/low
    sont donc réalistes : le moteur (liq sur high, TP sur low) s'approche du
    monitoring CONTINU — c'est le jeu de contrôle adapté à H4 (contrairement à
    `generate_gbm_daily`, déclarée non fiable pour les liquidations intra-barre).

    DEDUCE : les closes horaires suivent exactement un GBM (μ_hourly, σ_hourly)
    → les rendements logs sont iid N(μ_hourly, σ_hourly).
    """
    if steps_per_hour < 1:
        raise ValueError("steps_per_hour doit être ≥ 1.")
    rng = np.random.default_rng(seed)

    sub_mu = mu_hourly / steps_per_hour
    sub_sigma = sigma_hourly / np.sqrt(steps_per_hour)
    total = n_hours * steps_per_hour
    r = rng.normal(sub_mu, sub_sigma, total)
    sub_close = start_price * np.exp(np.cumsum(r))
    sub_close = np.clip(sub_close, 1e-8, None)

    g = sub_close.reshape(n_hours, steps_per_hour)
    close = g[:, -1]
    high = g.max(axis=1)
    low = g.min(axis=1)
    prev_last = sub_close[steps_per_hour - 1::steps_per_hour]
    open_ = np.empty(n_hours)
    open_[0] = start_price
    open_[1:] = prev_last[:-1]

    idx = pd.date_range("2020-01-01", periods=n_hours, freq="h", tz="UTC")
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=idx,
    )
    df.index.name = "open_time"
    return df


def save_synthetic_dataset(
    path: str,
    seed: int = 42,
    mu_daily: float = -0.002,
    sigma_daily: float = 0.04,
    n_days: int = 365,
    start_price: float = 100.0,
) -> dict:
    """Génère et sauvegarde un jeu GBM avec provenance marquée 'synthetic'.

    La provenance contient les paramètres EXACTS du générateur : toute analyse
    sur ce jeu peut être recalculée à l'identique (DEDUCE : même seed + mêmes
    paramètres -> même série).
    """
    df = generate_gbm_daily(
        start_price=start_price, n_days=n_days,
        mu_daily=mu_daily, sigma_daily=sigma_daily, seed=seed,
    )
    meta = save_with_provenance(
        df, path,
        source="synthetic-gbm",
        extra={
            "kind": "synthetic",
            "generator": "synthetic_gbm.generate_gbm_daily",
            "params": {
                "start_price": start_price,
                "n_days": n_days,
                "mu_daily": mu_daily,
                "sigma_daily": sigma_daily,
                "seed": seed,
            },
            "warning": ("Données de CONTRÔLE étiquetées synthetic. "
                        "Jamais utilisables comme performance historique."),
        },
    )
    return meta


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "data/SOLUSDT_GBM_control.csv"
    m = save_synthetic_dataset(out)
    print(f"Contrôle GBM écrit : {out}")
    print(f"  bars={m['bars']}  params={m['params']}")
