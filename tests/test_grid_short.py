from __future__ import annotations

import pytest

from src.simulator.engine import Bar
from src.strategy.grid_short import GridConfig, ShortGridStrategy


def bar(close, high=None, low=None, ts=0):
    high = close if high is None else high
    low = close if low is None else low
    import pandas as pd

    return Bar(ts=pd.Timestamp("2020-01-02") + pd.Timedelta(hours=ts),
               open=close, high=high, low=low, close=close)


@pytest.fixture
def cfg():
    return GridConfig(grid_size=2, grid_ratio=0.05, qty_sol=10.0, leverage=5.0)


@pytest.fixture
def strat(cfg):
    return ShortGridStrategy(cfg)


def test_config_valide_impose_contraintes():
    base = dict(grid_size=2, grid_ratio=0.05, qty_sol=10.0, leverage=5.0)
    for field, bad in [("grid_size", 0), ("grid_ratio", 0.0), ("grid_ratio", -1),
                       ("qty_sol", 0.0), ("leverage", 1.0)]:
        cfg = dict(base)
        cfg[field] = bad
        with pytest.raises(ValueError):
            GridConfig(**cfg)


def test_premiere_barre_pose_l_ancre_sans_signal(strat):
    out = strat.on_bar(bar(close=100.0))
    assert strat.anchor == 100.0
    assert strat.levels == pytest.approx([105.0, 110.0])
    assert out == []


def test_high_atteint_un_niveau_declenche_au_close(strat):
    strat.on_bar(bar(close=100.0))
    out = strat.on_bar(bar(close=100.0, high=106.0))
    assert len(out) == 1
    mark, sig = out[0]
    assert mark == pytest.approx(100.0)          # G3 : exécution au close
    assert sig.qty == 10.0
    assert sig.leverage == 5.0
    assert sig.tp_distance == pytest.approx(0.05)


def test_un_seul_signal_par_barre_meme_si_plusieurs_niveaux(strat):
    strat.on_bar(bar(close=100.0))
    out = strat.on_bar(bar(close=100.0, high=112.0))   # franchit 105 et 110
    assert len(out) == 1                                # G6
    assert out[0][0] == pytest.approx(100.0)


def test_niveau_depense_non_renvendu(strat):
    strat.on_bar(bar(close=100.0))
    strat.on_bar(bar(close=100.0, high=106.0))
    # high dépasse à nouveau le niveau 1 (dépensé) mais pas le niveau 2
    out = strat.on_bar(bar(close=100.0, high=109.0))
    assert out == []


def test_rea_anchor_bas_sur_cassure_du_close(strat):
    strat.on_bar(bar(close=100.0))
    strat.on_bar(bar(close=100.0, high=106.0))   # déclenche (dépense le niveau 105)
    # close < 100·(1−0.05) = 95 → ré-ancre à 94
    out = strat.on_bar(bar(close=94.0, high=95.0))
    assert strat.anchor == 94.0
    assert strat.levels == pytest.approx([98.7, 103.4])
    # le close 94 est sous le niveau 98.7 : high 95 ne l'atteint pas → pas de signal
    assert out == []


def test_rea_anchor_haut_sur_cassure_du_haut_de_bande(strat):
    strat.on_bar(bar(close=100.0))
    # seuil haut = 100·(1 + 3·0.05) = 115
    strat.on_bar(bar(close=120.0))
    assert strat.anchor == 120.0
    assert strat.levels == pytest.approx([126.0, 132.0])


def test_rea_anchor_ouvre_sur_nouveaux_niveaux(strat):
    strat.on_bar(bar(close=100.0))
    strat.on_bar(bar(close=94.0))                # ré-ancre à 94 (niveaux 98.7, 103.4)
    out = strat.on_bar(bar(close=94.0, high=99.0))
    assert len(out) == 1
    assert out[0][0] == pytest.approx(94.0)      # exécution au close, pas au niveau


def test_determinisme_deux_runs_identiques(strat, cfg):
    seq = [bar(close=100.0), bar(close=100.0, high=106.0), bar(close=99.0, high=99.0),
           bar(close=94.0, high=95.0), bar(close=94.0, high=99.0)]

    def collect(st):
        return [(m, s.qty, s.leverage, s.tp_distance)
                for b in seq for m, s in st.on_bar(b)]

    a = ShortGridStrategy(cfg)
    b = ShortGridStrategy(cfg)
    assert collect(a) == collect(b)
