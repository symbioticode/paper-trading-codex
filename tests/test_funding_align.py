"""
Tests de l'alignement funding/barres — écrits depuis la SPEC de
src/market/funding.funding_map_for_hourly_bars.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.market.funding import funding_map_for_hourly_bars


def test_alignement_funding_sur_barres_h():
    # barres de 00:00 à 09:00 (10h) : couvrent le funding de 00 et 08, pas 16
    bars = pd.date_range("2020-01-02 00:00", periods=10, freq="h", tz="UTC")
    funding_idx = pd.to_datetime([
        "2020-01-02 00:00:00.004",
        "2020-01-02 08:00:00.001",
        "2020-01-02 16:00:00.003",
    ], utc=True)
    funding = pd.DataFrame({"funding_rate": [0.001, -0.0005, 0.0001]},
                           index=funding_idx)
    out = funding_map_for_hourly_bars(funding, bars)
    assert list(out.index.hour) == [0, 8]
    assert out.iloc[0] == pytest.approx(0.001)
    assert out.iloc[1] == pytest.approx(-0.0005)


def test_alignement_doublon_intra_heure_garde_dernier():
    bars = pd.date_range("2020-01-02 00:00", periods=2, freq="h", tz="UTC")
    funding_idx = pd.to_datetime([
        "2020-01-02 00:00:00.000",
        "2020-01-02 00:00:00.500",
    ], utc=True)
    funding = pd.DataFrame({"funding_rate": [0.001, 0.002]}, index=funding_idx)
    out = funding_map_for_hourly_bars(funding, bars)
    assert out.iloc[0] == pytest.approx(0.002)
