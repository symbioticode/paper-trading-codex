from __future__ import annotations

import math

import pytest

from src.risk.moments import (
    estimate_moments,
    log_returns,
    rolling_moments,
    wilson_ci,
)


def test_log_returns_formule_et_longueur():
    r = log_returns([1.0, 2.0, 4.0])
    assert r == pytest.approx([math.log(2.0), math.log(2.0)])


def test_log_returns_rejette_entrees_invalides():
    with pytest.raises(ValueError):
        log_returns([1.0])                      # trop court
    with pytest.raises(ValueError):
        log_returns([1.0, -2.0])                # prix négatif
    with pytest.raises(ValueError):
        log_returns([[1.0], [2.0]])             # non 1D


def test_estimation_sur_gbm_contient_les_vrais_parametres():
    # GBM synthétique : μ=0.0005/h, σ=0.02/h, n=4000 → ICs serrés
    import numpy as np

    rng = np.random.default_rng(7)
    sigma, mu = 0.02, 0.0005
    steps = 4000
    r = mu + sigma * rng.standard_normal(steps)
    close = 100.0 * np.exp(np.cumsum(r))
    est = estimate_moments(close, alpha_ci=0.05)

    assert est.n == steps - 1           # len(rendements logs)
    assert est.mu_ci[0] <= mu <= est.mu_ci[1]
    assert est.sigma_ci[0] <= sigma <= est.sigma_ci[1]
    assert est.sigma_ci[0] < est.sigma < est.sigma_ci[1]


def test_estimation_rejette_ci_incoherent():
    import numpy as np

    with pytest.raises(ValueError):
        estimate_moments(np.array([1.0, 2.0]), alpha_ci=2.0)


def test_rolling_moments_forme_et_last():
    import numpy as np
    import pandas as pd

    close = 100.0 * 1.0005 ** np.arange(2000)     # drift constant → rendements ~ constants
    out = rolling_moments(close, window=100)
    assert isinstance(out, pd.DataFrame)
    assert list(out.columns) == ["mu", "sigma"]
    assert len(out) == 1900
    assert out["mu"].iloc[-1] > 0
    assert out["sigma"].iloc[-1] < 1e-12          # rendements constants → vol ~ 0


def test_wilson_ci_extremes_et_centre():
    lo0, hi0 = wilson_ci(0, 100)
    assert lo0 == pytest.approx(0.0)
    assert hi0 > 0.0
    lon, hin = wilson_ci(100, 100)
    assert lon < 1.0
    assert hin == pytest.approx(1.0)
    lo, hi = wilson_ci(50, 100)
    assert lo <= 0.5 <= hi
    assert lo < hi


def test_wilson_ci_rejette_arguments_invalides():
    with pytest.raises(ValueError):
        wilson_ci(10, 0)
    with pytest.raises(ValueError):
        wilson_ci(-1, 10)
    with pytest.raises(ValueError):
        wilson_ci(11, 10)
    with pytest.raises(ValueError):
        wilson_ci(5, 10, z=0.0)
