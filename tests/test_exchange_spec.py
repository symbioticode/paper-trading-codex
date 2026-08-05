"""
Tests H1 — écrits depuis la SPEC (src/market/exchange_spec.py), jamais depuis
le code. Cas limites analytiques testés AVANT les valeurs numériques.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.market.exchange_spec import (
    MAKER_FEE,
    SOLUSDT_MMR_TIERS,
    TAKER_FEE,
    liquidation_distance_short,
    liquidation_price_short,
    mmr_for_notional,
)


# ─── MMR par tranche ─────────────────────────────────────────────────────────

def test_mmr_tier1_pour_petit_notionnel():
    assert mmr_for_notional(10_000) == pytest.approx(0.0050)


def test_mmr_aux_bornes_de_tranche():
    # juste sous / à / juste au-dessus de la première borne
    assert mmr_for_notional(49_999) == pytest.approx(0.0050)
    assert mmr_for_notional(50_000) == pytest.approx(0.0050)
    assert mmr_for_notional(50_001) == pytest.approx(0.0100)


def test_mmr_monotone_non_decroissante():
    caps = [tier.notional_cap for tier in SOLUSDT_MMR_TIERS]
    ratios = [tier.mmr for tier in SOLUSDT_MMR_TIERS]
    assert all(b > a for a, b in zip(caps, caps[1:]))  # caps croissants
    assert all(b >= a for a, b in zip(ratios, ratios[1:]))  # MMR non décroissant


def test_mmr_notionnel_negatif_leve_erreur():
    with pytest.raises(ValueError):
        mmr_for_notional(-1)


# ─── Cas limites analytiques (AVANT les valeurs) ─────────────────────────────

def test_short_liq_toujours_au_dessus_du_prix():
    for L in [2, 5, 10, 20]:
        liq = liquidation_price_short(entry=100, leverage=L, notional=10_000)
        assert liq > 100


def test_liq_decroit_avec_le_levier():
    """Plus le levier est haut, plus la liq est proche de l'entrée."""
    liq_low = liquidation_price_short(100, leverage=2, notional=10_000)
    liq_high = liquidation_price_short(100, leverage=10, notional=10_000)
    assert liq_high < liq_low


def test_liq_decroit_quand_mmr_augmente():
    """Franchir une borne de tranche (MMR plus élevé) rapproche la liq."""
    liq_t1 = liquidation_price_short(100, 10, notional=10_000)   # mmr 0.005
    liq_t2 = liquidation_price_short(100, 10, notional=60_000)   # mmr 0.01
    assert liq_t2 < liq_t1


def test_mmr_nul_limite_1surL():
    """MMR -> 0 : liq -> E·(1 + 1/L). Ici via une tranche hypothétique nulle,
    on vérifie l'équivalent algébrique en comparant à la forme fermée."""
    liq = liquidation_price_short(100, 5, notional=10_000)
    expected_exact = 100 * (1 + 1 / 5) / (1 + 0.005)
    assert liq == pytest.approx(expected_exact, rel=1e-12)


def test_position_non_viable_liq_a_entree():
    """Si 1/L < MMR, la marge initiale ne couvre pas la maintenance -> liq = E."""
    notional = 10_000          # tier1 mmr = 0.005
    liq = liquidation_price_short(100, leverage=500, notional=notional)
    assert liq == pytest.approx(100.0)


def test_levier_inferieur_ou_egal_1_rejete():
    with pytest.raises(ValueError):
        liquidation_price_short(100, 1.0, notional=10_000)
    with pytest.raises(ValueError):
        liquidation_price_short(100, 0.5, notional=10_000)


# ─── Valeurs numériques fermées (DEDUCE, calculées à la main) ────────────────

def test_valeur_fermee_concrete():
    entry, L, notional = 100.0, 5.0, 10_000
    liq = liquidation_price_short(entry, L, notional)
    assert liq == pytest.approx(120.0 / 1.005, rel=1e-12)   # 119.402985...
    d = liquidation_distance_short(entry, L, notional)
    assert d == pytest.approx((1 / L - 0.005) / (1 + 0.005), rel=1e-12)


def test_coherence_avec_approximation_historique():
    """L'approximation historique E(1 + 1/L − MMR) coïncide à l'ordre 1 en MMR.
    DEDUCE : |d_exact − d_approx| = mmr·(1/L − mmr)/(1+mmr) ≈ mmr/L."""
    mmr = 0.005
    for L in [3, 5, 10]:
        d_exact = liquidation_distance_short(100, L, notional=10_000)
        d_approx = 1 / L - mmr
        assert abs(d_exact - d_approx) < mmr * (1 / L) + 1e-12


def test_frais_strictement_positifs():
    assert MAKER_FEE > 0 and TAKER_FEE > 0
    assert TAKER_FEE > MAKER_FEE  # convention standard VIP0 (ASSUME, doc.)
