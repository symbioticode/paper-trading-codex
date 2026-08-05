from __future__ import annotations

import pandas as pd
import pytest

from src.simulator.engine import Bar
from src.simulator.runner import RunConfig, RunResult, run_backtest
from src.strategy.grid_short import GridConfig, ShortGridStrategy


def bar(close, high=None, low=None, ts=0):
    high = close if high is None else high
    low = close if low is None else low
    return Bar(ts=pd.Timestamp("2020-01-02") + pd.Timedelta(hours=ts),
               open=close, high=high, low=low, close=close)


@pytest.fixture
def cfg():
    return GridConfig(grid_size=2, grid_ratio=0.05, qty_sol=10.0, leverage=5.0)


def test_cycle_complet_ouvre_ferme_au_tp_et_gagne_la_taille_de_grille(cfg):
    # grille ancrée à 100 (niveaux 105, 110) ; barre 2 franchit 105 → ouverture
    # au close 100 ; barre 3, le low 93 touche le TP 95 (0.95·entry).
    seq = [bar(close=100.0), bar(close=100.0, high=106.0), bar(close=94.0, low=93.0)]
    res = run_backtest(seq, ShortGridStrategy(cfg))

    assert res.n_signals == 1
    assert res.n_opened == 1
    assert res.n_skipped_cash == 0
    assert len(res.engine.trades) == 1
    t = res.engine.trades[0]
    assert t.reason == "take_profit"
    assert t.entry == pytest.approx(100.0)       # R1 : exécution au close
    assert t.exit == pytest.approx(100.0 * 0.95)
    assert t.gross_pnl == pytest.approx((100 - 95) * 10 * 5)
    assert t.net_pnl == pytest.approx((100 - 95) * 10 * 5 - 1000 * 0.0002 - 1000 * 0.0004)
    assert res.engine.equity_usd() == pytest.approx(10_000 + t.net_pnl)


def test_liquidation_par_touch_sur_high_apres_ouverture(cfg):
    # grid_size=1 : niveau 105 franchi à la barre 2 → ouverture au close 101 ;
    # barre 3 : high 130 ≥ liq(101)·(1+d) ≈ 120.6 → liquidation.
    c = GridConfig(grid_size=1, grid_ratio=0.05, qty_sol=10.0, leverage=5.0)
    seq = [bar(close=100.0), bar(close=101.0, high=130.0), bar(close=101.0, high=130.0)]
    res = run_backtest(seq, ShortGridStrategy(c))

    assert res.n_opened == 1
    assert res.engine.liquidations == 1
    t = res.engine.trades[0]
    assert t.reason == "liquidation"
    margin = 101.0 * 10 / 5
    assert t.net_pnl == pytest.approx(-margin - 1010 * 0.0002)
    assert res.engine.equity_usd() == pytest.approx(10_000 - margin - 1010 * 0.0002)


def test_funding_credite_le_short_dans_le_runner(cfg):
    # R1 : la position ouverte à la barre 2 reçoit le funding de la barre 3.
    seq = [bar(close=100.0, ts=0), bar(close=100.0, high=106.0, ts=1),
           bar(close=94.0, low=93.0, ts=2)]
    fund = pd.Series([0.001], index=[pd.Timestamp("2020-01-02 02:00")])
    res = run_backtest(seq, ShortGridStrategy(cfg), funding_map=fund)
    t = res.engine.trades[0]
    assert t.funding == pytest.approx(1000.0 * 0.001)
    assert t.net_pnl == pytest.approx(
        (100 - 95) * 10 * 5 - 1000 * 0.0002 - 1000 * 0.0004 + 1.0)


def test_policy_resize_reduit_la_taille_au_lieu_de_skipper(cfg):
    # R5 : capital 100 < marge+frais (200+), la position est OUVERTE avec une
    # taille réduite (qty ≈ 100·0.995/20.02 ≈ 4.97) au lieu d'être écartée.
    seq = [bar(close=100.0), bar(close=100.0, high=106.0)]
    rcfg = RunConfig(initial_capital=100.0)
    res = run_backtest(seq, ShortGridStrategy(cfg), cfg=rcfg)
    assert res.n_skipped_cash == 0
    assert res.n_opened == 1
    assert len(res.engine.positions) == 1
    pos = res.engine.positions[0]
    assert pos.qty == pytest.approx(100.0 * 0.995 / (100.0 / 5 + 100.0 * 0.0002))
    assert res.engine.cash_usd == pytest.approx(
        100.0 - (pos.qty * 100.0 / 5 + pos.qty * 100.0 * 0.0002))


def test_plafond_max_positions_skip_les_surplus(cfg):
    # barre 2 déclenche le niveau 1 (1 position) ; barre 3 franchit le niveau 2
    # → signal supplémentaire bloqué par max_positions=1.
    seq = [bar(close=100.0), bar(close=100.0, high=106.0), bar(close=100.0, high=112.0)]
    rcfg = RunConfig(max_positions=1)
    res = run_backtest(seq, ShortGridStrategy(cfg), cfg=rcfg)
    assert res.n_signals == 2
    assert res.n_opened == 1
    assert res.n_skipped_max_pos == 1
    assert len(res.engine.positions) == 1


def test_invariant_somme_issues_signaux(cfg):
    seq = [bar(close=100.0), bar(close=100.0, high=112.0), bar(close=90.0, high=95.0)]
    res = run_backtest(seq, ShortGridStrategy(cfg), cfg=RunConfig(initial_capital=100.0))
    assert res.n_signals == res.n_opened + res.n_skipped_cash + res.n_skipped_cap + res.n_skipped_max_pos


def test_can_open_distingue_cash_et_notional_cap():
    eng = run_backtest([bar(close=100.0)], ShortGridStrategy(GridConfig(
        grid_size=1, grid_ratio=0.05, qty_sol=10.0, leverage=5.0))).engine

    from src.simulator.engine import OpenSignal

    sig = OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.05)
    eng.cash_usd = 100.0
    assert eng.can_open(sig, 100.0) == (False, "cash")

    eng.cash_usd = 10_000.0
    eng.notional_cap = 500.0
    assert eng.can_open(sig, 100.0) == (False, "notional_cap")

    eng.notional_cap = 49_000.0
    assert eng.can_open(sig, 100.0) == (True, "ok")
