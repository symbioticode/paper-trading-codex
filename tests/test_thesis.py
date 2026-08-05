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
    #
    # Capital volontairement ABONDANT (REV2) : H4 mesure la fréquence de
    # liquidation (géométrie L/s), pas la solvabilité du portefeuille. Sur GBM
    # à dérive positive une grille SHORT perd de l'argent ; à capital 10 000 le
    # skip cash (R5) tronque l'échantillon et le contrôle échoue pour une
    # raison de portefeuille, pas de machinerie. À capital abondant le contrôle
    # isole la machinerie (estimation → prédiction → simulateur → test).
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
    run_cfg = RunConfig(initial_capital=1_000_000.0)

    report = validate_thesis(
        closes, bars, windows, grid_cfg, run_cfg=run_cfg,
        predictor=lambda mu, sig, L, s: predict_discrete(
            0.0002, 0.025, L, s, steps_per_hour=30, n_paths=5000, seed=0),
    )
    assert report.passes
    assert report.n_skipped == 0
    assert report.global_bucket.testable


def _crafted_bars():
    """Scénario W3/V7 écrit depuis le TEXTE du protocole (pas depuis le code) :

      W3 : une position est attribuée à la fenêtre de test où elle s'OUVRE et
           suivie jusqu'à résolution ; les positions encore ouvertes à la fin
           du jeu sont CENSURÉES et comptées à part (jamais au dénominateur).

    Grille : grid_size=1, s=2%, L=5, qty=10, capital 10 000.
    - barres 0-4  : plat 100 (ancre A=100, niveau 102).
    - barre 5     : high=103 ≥ 102 → entrée au close 103 (fenêtre d'ouverture :
                    barre 5 ∈ [0,20) = train → HORS fenêtre de test).
    - barre 6     : low=99 ≤ TP 100.94 → TP. Trade RÉSOLU, n_hors_fenetres=1.
    - barre 7     : close=97 ≤ A·0.98=98 → ré-ancre à 97 (niveau 98.94).
    - barres 8-88 : plat 97.5 → aucun trigger (97.5 < 98.94), aucune résolution
                    (97.5 dans la bande), aucun ré-ancrage.
    - barre 89    : high=99 ≥ 98.94 → entrée au close 98.5 (barre 89 ∈ fenêtre
                    de test 3). TP=96.53, liq≈117.6.
    - barres 90-99 : oscille autour de 97.5 (low ≥ 96.9 > TP 96.53) → la
                    position reste OUVERTE à la fin : censurée (V7),
                    n_open_at_end=1, JAMAIS au dénominateur.
    L'oscillation (97.5 ± 0.5) garde chaque train σ>0 (exigence de
    p_pred_cont) sans déclencher de nouveau signal (high ≤ 98.2 < 98.94),
    sans résolution (low > 96.53) et sans ré-ancrage (closes ∈ [95.06, 100.88]).
    """
    closes = [100.0] * 5 + [103.0, 99.0, 97.0]
    for k in range(8, 100):
        closes.append(98.5 if k == 89 else 97.5 + 0.4 * math.sin(k))
    highs = [c + (0.2 if 8 <= i < 100 and i != 89 else 0.0) for i, c in enumerate(closes)]
    lows = [c - (0.2 if 8 <= i < 100 and i != 89 else 0.0) for i, c in enumerate(closes)]
    highs[5] = 103.0
    highs[89] = 99.0
    lows[6] = 99.0
    bars = [
        Bar(ts=i, open=c, high=h, low=l, close=c)
        for i, (c, h, l) in enumerate(zip(closes, highs, lows))
    ]
    return closes, bars


def test_validate_thesis_w3v7_censure_positions_ouvertes():
    closes, bars = _crafted_bars()
    windows = build_windows(len(bars), 20, 20)
    grid_cfg = GridConfig(grid_size=1, grid_ratio=0.02, qty_sol=10.0, leverage=5.0)
    report = validate_thesis(
        closes, bars, windows, grid_cfg,
        run_cfg=RunConfig(initial_capital=10_000.0),
        predictor=lambda mu, sig, L, s: 0.1,
    )
    # V7 : la position de la barre 89 reste ouverte en fin de jeu → censurée,
    # comptée à part, JAMAIS ajoutée au dénominateur (aucune fenêtre n'a n>0).
    assert report.n_open_at_end == 1
    assert report.n_hors_fenetres == 1      # trade barre 5, ouvert hors fenêtre
    assert all(w.n_positions == 0 for w in report.windows)
    assert report.global_bucket.n == 0
