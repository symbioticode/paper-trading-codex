from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.simulator.engine import Bar
from src.simulator.runner import RunConfig, run_backtest
from src.strategy.grid_short import GridConfig, ShortGridStrategy
from src.validation.thesis import cluster_robust_test, predict_discrete, validate_thesis
from src.validation.windows import build_windows


def bar(close, high=None, low=None, ts=0):
    high = close if high is None else high
    low = close if low is None else low
    return Bar(ts=pd.Timestamp("2020-01-02") + pd.Timedelta(hours=ts),
               open=close, high=high, low=low, close=close)


def test_cluster_robust_test_basique():
    # H0 trivial : toutes les fenêtres collent à la prédiction → accepté
    k_w = [5, 6, 4, 7]
    n_w = [50, 50, 50, 50]
    pred_w = [0.11, 0.11, 0.11, 0.11]
    p, pred, v, margin, ok = cluster_robust_test(k_w, n_w, pred_w)
    assert p == pytest.approx(22 / 200)
    assert pred == pytest.approx(0.11)
    assert ok
    assert margin > 0.0


def test_cluster_robust_test_w1_non_testable():
    p, pred, v, margin, ok = cluster_robust_test([3], [30], [0.1])
    assert not ok
    assert math.isnan(p)


def test_cluster_robust_test_ecart_net_refuse():
    # p̂ ~ 0.5 contre P̂ ~ 0.1 sur plusieurs fenêtres stables → rejeté
    k_w = [25, 26, 24, 27]
    n_w = [50, 50, 50, 50]
    pred_w = [0.1, 0.1, 0.1, 0.1]
    _, _, _, _, ok = cluster_robust_test(k_w, n_w, pred_w)
    assert not ok


def test_predict_discrete_domaine():
    assert 0.0 < predict_discrete(0.0, 0.03, 5.0, 0.02) < 1.0
    p_fin = predict_discrete(0.0005, 0.03, 5.0, 0.02, steps_per_hour=300, n_paths=5000)
    assert 0.0 < p_fin < 0.5


def test_validate_thesis_controle_gbm_passe():
    # contrôle GBM OHLC court mais suffisant : le modèle est vrai par
    # construction, H4 doit passer.
    from data.synthetic_gbm import generate_gbm_hourly_ohlc

    df = generate_gbm_hourly_ohlc(
        n_hours=9000, mu_hourly=0.0002, sigma_hourly=0.025,
        steps_per_hour=30, seed=11,
    )
    closes = df["close"].to_numpy(dtype=float)
    bars = [Bar(ts=i, open=r["open"], high=r["high"], low=r["low"],
                close=r["close"]) for i, r in df.iterrows()]
    windows = build_windows(len(bars), 2000, 1000)
    grid_cfg = GridConfig(grid_size=1, grid_ratio=0.02, qty_sol=10.0, leverage=5.0)
    run_cfg = RunConfig(initial_capital=10_000.0)

    report = validate_thesis(
        closes, bars, windows, grid_cfg, run_cfg=run_cfg,
        predictor=lambda mu, sig, L, s: predict_discrete(
            0.0002, 0.025, L, s, steps_per_hour=30, n_paths=5000, seed=0),
    )
    assert report.passes
    assert report.n_skipped == 0
    assert report.global_bucket.testable
