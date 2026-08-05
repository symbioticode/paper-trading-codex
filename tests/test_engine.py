"""
Tests du moteur d'exécution — écrits depuis la SPEC (src/simulator/engine.py),
conventions E1..E9. Rattachés : H5 (cohérence du numéraire), support H4.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.market.exchange_spec import liquidation_price_short
from src.simulator.engine import (
    Bar,
    OpenSignal,
    SimulationEngine,
    bars_from_frame,
)


def bar(close: float, high: float | None = None, low: float | None = None,
        ts="2020-01-01 00:00") -> Bar:
    h = close if high is None else high
    l = close if low is None else low
    return Bar(ts=pd.Timestamp(ts, tz="UTC"), open=close, high=h, low=l, close=close)


def make_engine(capital=10_000.0, **kw) -> SimulationEngine:
    return SimulationEngine(initial_capital=capital, **kw)


# ─── E4/E5 : comptabilité d'une position TP ──────────────────────────────────

def test_pnl_take_profit_exact():
    eng = make_engine()
    eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02),
                   mark=100.0, ts=pd.Timestamp("2020-01-01", tz="UTC"))
    pos = eng.positions[0]
    assert pos.entry == 100.0
    assert pos.tp_price == 98.0
    # high ne liquide pas, low touche le TP -> fermeture à 98
    eng.on_bar(bar(close=97.0, high=101.0, low=97.0))
    t = eng.trades[-1]
    assert t.reason == "take_profit"
    # gross = (100−98)·10·5 = 100 ; fees : 1000·0.0002 + 1000·0.0004
    assert t.gross_pnl == pytest.approx(100.0)
    assert t.net_pnl == pytest.approx(100 - 0.2 - 0.4)
    assert eng.equity_usd() == pytest.approx(10_000 + t.net_pnl, rel=1e-12)

# ─── E5 : liquidation ────────────────────────────────────────────────────────

def test_liquidation_pert_toute_la_marge():
    eng = make_engine()
    eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02),
                   mark=100.0, ts=pd.Timestamp("2020-01-01", tz="UTC"))
    liq = eng.positions[0].liq_price
    assert liq == pytest.approx(120.0 / 1.005, rel=1e-12)

    eng.on_bar(bar(close=liq + 1, high=liq + 1, low=liq - 1))
    assert eng.liquidations == 1
    t = eng.trades[-1]
    assert t.reason == "liquidation"
    assert t.net_pnl == pytest.approx(-200.0 - 0.2)   # −marge − fraise entrée
    assert eng.equity_usd() == pytest.approx(10_000 - 200.2, rel=1e-12)


# ─── E6 : même barre, liq gagne ──────────────────────────────────────────────

def test_meme_barre_liq_avant_tp():
    eng = make_engine()
    eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02),
                   mark=100.0, ts=pd.Timestamp("2020-01-01", tz="UTC"))
    # high dépasse la liq ET low dépasse le TP dans la même barre
    eng.on_bar(bar(close=100, high=130.0, low=95.0))
    assert eng.liquidations == 1
    assert eng.trades[-1].reason == "liquidation"


# ─── E7 : funding ────────────────────────────────────────────────────────────

def test_short_recoit_si_funding_positif():
    eng = make_engine()
    eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02),
                   mark=100.0, ts=pd.Timestamp("2020-01-01", tz="UTC"))
    # funding rate 0.001 (>0) : le short REÇOIT 0.001×notional = 1.0
    eng.on_bar(bar(close=99.0, low=99.0), funding_rate=0.001)
    assert eng.positions[0].funding == pytest.approx(1.0)
    eng.on_bar(bar(close=98.0, low=98.0))   # ferme au TP
    t = eng.trades[-1]
    assert t.funding == pytest.approx(1.0)
    assert t.net_pnl == pytest.approx(100 - 0.2 - 0.4 + 1.0)

def test_funding_nul_sans_effet():
    eng = make_engine()
    eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02),
                   mark=100.0, ts=pd.Timestamp("2020-01-01", tz="UTC"))
    eng.on_bar(bar(close=100), funding_rate=0.0)
    assert eng.positions[0].funding == 0.0


# ─── H5 : invariance de la somme des PnL ─────────────────────────────────────

def test_somme_pnl_egale_equity_moins_capital():
    eng = make_engine()
    ts0 = pd.Timestamp("2020-01-01", tz="UTC")
    # cycle 1 : TP
    eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02), 100.0, ts0)
    eng.on_bar(bar(close=97, high=101, low=97))
    # cycle 2 : liquidation
    eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02), 100.0, ts0)
    eng.on_bar(bar(close=130, high=130, low=90))
    # cycle 3 : TP avec funding
    eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02), 100.0, ts0)
    eng.on_bar(bar(close=99, low=99), funding_rate=0.001)
    eng.on_bar(bar(close=97, high=101, low=97))

    assert len(eng.positions) == 0
    realized = sum(t.net_pnl for t in eng.trades)
    assert eng.equity_usd() == pytest.approx(10_000 + realized, rel=1e-9)


# ─── E8 : slippage ───────────────────────────────────────────────────────────

def test_slippage_entree_short():
    eng = make_engine(slip_bps=50)   # 0.5%
    eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02),
                   mark=100.0, ts=pd.Timestamp("2020-01-01", tz="UTC"))
    assert eng.positions[0].entry == pytest.approx(99.5)


def test_liq_prix_reflete_slippage():
    eng = make_engine(slip_bps=50)
    eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02),
                   mark=100.0, ts=pd.Timestamp("2020-01-01", tz="UTC"))
    pos = eng.positions[0]
    assert pos.liq_price == pytest.approx(
        liquidation_price_short(99.5, 5.0, 10 * 99.5), rel=1e-12)


# ─── E9 : signaux invalides ──────────────────────────────────────────────────

def test_signal_qty_negative_rejete():
    eng = make_engine()
    with pytest.raises(ValueError):
        eng.open_short(OpenSignal(qty=-1.0, leverage=5.0, tp_distance=0.02),
                       mark=100.0, ts=pd.Timestamp("2020-01-01", tz="UTC"))


def test_cash_insuffisant_rejete():
    eng = make_engine(capital=100.0)
    with pytest.raises(ValueError, match="Cash insuffisant"):
        eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02),
                       mark=100.0, ts=pd.Timestamp("2020-01-01", tz="UTC"))


def test_notionnel_hors_cap_rejete():
    eng = make_engine(notional_cap=500.0)
    with pytest.raises(ValueError, match="hors de la tranche"):
        eng.open_short(OpenSignal(qty=10.0, leverage=5.0, tp_distance=0.02),
                       mark=100.0, ts=pd.Timestamp("2020-01-01", tz="UTC"))


# ─── bars_from_frame ─────────────────────────────────────────────────────────

def test_bars_from_frame_valide():
    idx = pd.date_range("2020-01-01", periods=3, freq="h", tz="UTC")
    df = pd.DataFrame({
        "open": [100.0, 101.0, 102.0],
        "high": [101.0, 102.0, 103.0],
        "low": [99.0, 100.0, 101.0],
        "close": [100.5, 101.5, 102.5],
    }, index=idx)
    bars = bars_from_frame(df)
    assert len(bars) == 3
    assert bars[0].ts == idx[0]


def test_bars_from_frame_colonne_manquante():
    idx = pd.date_range("2020-01-01", periods=2, freq="h", tz="UTC")
    df = pd.DataFrame({"open": [1.0, 1.0], "high": [1.0, 1.0],
                       "low": [1.0, 1.0]}, index=idx)
    with pytest.raises(ValueError, match="Colonne manquante"):
        bars_from_frame(df)
