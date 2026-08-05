from __future__ import annotations

import pytest

from src.validation.windows import Window, build_windows, tag_opening_indices


def test_fenetres_adjacentes_non_chevauchantes():
    ws = build_windows(n_total=5000, n_train=1000, n_test=500)
    assert len(ws) == 8  # 8 fenêtres de 500 : [1000,6000)
    for a, b in zip(ws, ws[1:]):
        assert a.test_end == b.test_start          # adjacentes
        assert a.test_start < b.test_start         # non chevauchantes
        assert a.train_end == a.test_start         # W2 : train juste avant
        assert a.train_start == a.test_start - 1000


def test_fenetres_trop_courtes_levent():
    with pytest.raises(ValueError):
        build_windows(n_total=500, n_train=1000, n_test=100)
    with pytest.raises(ValueError):
        build_windows(n_total=100, n_train=0, n_test=50)


def test_tag_opening_indices_w3():
    ws = build_windows(n_total=310, n_train=100, n_test=50)
    # ouverture à la barre 120 (fenêtre 0), 180 (fenêtre 1), 95 (train initial)
    assert tag_opening_indices([120, 180, 95], ws) == [0, 1, -1]
    # queue non couverte (la dernière fenêtre s'arrête à 300)
    assert tag_opening_indices([305], ws) == [-1]


def test_tag_position_au_bord_fenetre():
    ws = [Window(id=0, train_start=0, train_end=10, test_start=10, test_end=20)]
    assert tag_opening_indices([10], ws) == [0]   # borne inf incluse
    assert tag_opening_indices([19], ws) == [0]   # borne sup exclue
    assert tag_opening_indices([20], ws) == [-1]
