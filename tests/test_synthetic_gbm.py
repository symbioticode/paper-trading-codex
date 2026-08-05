"""
Tests du générateur GBM de contrôle — écrits depuis la SPEC
(synthetic_gbm.py). Rattachés : H2 (contrôle à vérité connue).
"""

from __future__ import annotations

import numpy as np

from data.data_loader import validate_ohlcv
from data.synthetic_gbm import generate_gbm_daily, save_synthetic_dataset


def test_sortie_ohlcv_canonique():
    df = generate_gbm_daily(n_days=120, seed=1)
    report = validate_ohlcv(df)
    assert report.passed, report.summary()


def test_deterministe_meme_seed():
    a = generate_gbm_daily(n_days=50, seed=7)
    b = generate_gbm_daily(n_days=50, seed=7)
    assert a.equals(b)


def test_seed_different_serie_differente():
    a = generate_gbm_daily(n_days=50, seed=1)
    b = generate_gbm_daily(n_days=50, seed=2)
    assert not a.equals(b)


def test_vol_mesuree_proche_du_parametre():
    """INFER : la vol échantillonnée doit converger vers sigma_daily.
    ASSUME : tolérance large (n petit), vérification cible : n -> 10_000."""
    sigma = 0.04
    df = generate_gbm_daily(n_days=4000, sigma_daily=sigma, seed=3)
    log_ret = np.log(df["close"]).diff().dropna()
    assert abs(log_ret.std() - sigma) < 0.02


def test_drift_mesure_proche_du_parametre():
    mu = -0.002
    df = generate_gbm_daily(n_days=4000, mu_daily=mu, sigma_daily=0.04, seed=4)
    log_ret = np.log(df["close"]).diff().dropna()
    assert abs(log_ret.mean() - mu) < 0.01


def test_provenance_marquee_synthetic(tmp_path):
    out = tmp_path / "ctrl.csv"
    meta = save_synthetic_dataset(out, seed=11, n_days=30)
    assert meta["source"] == "synthetic-gbm"
    assert meta["kind"] == "synthetic"
    assert meta["params"]["seed"] == 11
    assert "warning" in meta
