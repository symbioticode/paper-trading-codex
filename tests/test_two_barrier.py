from __future__ import annotations

import math

import pytest

from src.risk.monte_carlo import simulate_two_barrier
from src.risk.two_barriers import (
    _prob_from_ab,
    max_leverage_for_alpha,
    prob_liquidation_from_L,
    prob_liquidation_short,
)


def test_cas_limite_drift_nul_barriere_equilibree():
    # μ=0 : P = a/(a+b) ; symétrie a=b ⇒ P=1/2
    assert _prob_from_ab(0.02, 0.02, 0.0, 0.03) == pytest.approx(0.5)
    assert _prob_from_ab(0.02, 0.08, 0.0, 0.03) == pytest.approx(0.02 / 0.10)


def test_cas_limites_drift_extreme():
    # μ→+∞ : liq presque sûre ; μ→−∞ : liq ~ impossible
    assert _prob_from_ab(0.02, 0.02, 1e6, 0.03) == pytest.approx(1.0, rel=1e-9)
    assert _prob_from_ab(0.02, 0.02, -1e6, 0.03) == pytest.approx(0.0, abs=1e-9)


def test_cas_limites_barrieres_degenerees():
    # b→0 : liq immédiate (P→1) ; a→0 : TP immédiat (P→0)
    assert _prob_from_ab(0.02, 1e-9, 0.0, 0.03) == pytest.approx(1.0, abs=1e-6)
    assert _prob_from_ab(1e-9, 0.02, 0.0, 0.03) == pytest.approx(0.0, abs=1e-6)


def test_invariance_unite_de_temps():
    # μ/σ² invariant : quotidien vs horaire donnent le même P(liq)
    p_h = _prob_from_ab(0.02, 0.08, 0.0005, 0.02)
    p_d = _prob_from_ab(0.02, 0.08, 0.0005 * 24, 0.02 * math.sqrt(24))
    assert p_h == pytest.approx(p_d, rel=1e-12)


def test_prob_liquidation_rejette_geometrie_invalide():
    with pytest.raises(ValueError):
        prob_liquidation_short(100.0, 99.0, 100.0, 0.0, 0.02)   # liq ≤ entry
    with pytest.raises(ValueError):
        prob_liquidation_short(100.0, 100.0, 110.0, 0.0, 0.02)  # tp = entry
    with pytest.raises(ValueError):
        prob_liquidation_short(100.0, 99.0, 110.0, 0.0, 0.0)    # σ = 0


def test_prob_liquidation_from_L_cohérent_avec_short():
    # L=5, s=2%, MMR=0.5% : liq ≈ E·(1+0.194), a=−ln(0.98), b=ln(1.194)
    p = prob_liquidation_from_L(5.0, 0.02, 0.0005, 0.03)
    d = (1 / 5 - 0.005) / 1.005
    a = -math.log(0.98)
    b = math.log(1 + d)
    assert p == pytest.approx(_prob_from_ab(a, b, 0.0005, 0.03), rel=1e-12)


def test_prob_liquidation_from_L_rejette_levier_impossible():
    with pytest.raises(ValueError):
        prob_liquidation_from_L(200.0, 0.02, 0.0, 0.03)   # 200 ≥ 1/0.005


def test_monte_carlo_ground_truth_rejoint_la_formule():
    # Params : σ=3%/h, μ=0.05%/h, a=ln(1/0.98), b=ln(1+0.194), N=10 000.
    gt = simulate_two_barrier(
        mu=0.0005, sigma=0.03, a=-math.log(0.98),
        b=math.log(1 + (0.2 - 0.005) / 1.005),
        n=10_000, dt=0.01, cap=200_000, seed=42,
    )
    assert gt.n_undecided == 0
    assert gt.passes(), (
        f"p̂={gt.p_hat:.4f} vs P={gt.p_pred:.4f}, tol 5σ={gt.max_error_5sigma:.4f}"
    )


def test_monte_carlo_ground_truth_drift_negatif():
    # μ<0 : P(liq) bien plus basse, MC doit la retrouver
    gt = simulate_two_barrier(
        mu=-0.001, sigma=0.03, a=-math.log(0.98),
        b=math.log(1 + (0.2 - 0.005) / 1.005),
        n=10_000, dt=0.01, cap=200_000, seed=1,
    )
    assert gt.passes()
    assert gt.p_hat < 0.10


def test_max_leverage_respecte_et_serre_le_budget_alpha():
    alpha, s, mu, sigma = 0.10, 0.02, 0.0005, 0.03
    Lstar = max_leverage_for_alpha(alpha, s, mu, sigma)
    assert Lstar is not None
    assert 1.0 < Lstar < 1.0 / 0.005
    assert prob_liquidation_from_L(Lstar, s, mu, sigma) <= alpha
    # juste au-dessus : budget dépassé
    assert prob_liquidation_from_L(Lstar + 1e-3, s, mu, sigma) > alpha


def test_max_leverage_decroit_en_volatilite_pour_drift_non_positif():
    # μ ≤ 0 : L* non-croissant en σ (décroissant ; constant à μ=0)
    for mu in [-0.002, -0.001, 0.0]:
        sigmas = [0.01, 0.02, 0.03, 0.06, 0.12]
        Ls = [max_leverage_for_alpha(0.10, 0.02, mu, s) for s in sigmas]
        assert all(b <= a + 1e-6 for a, b in zip(Ls, Ls[1:])), (mu, Ls)


def test_max_leverage_croit_en_volatilite_pour_drift_positif():
    # μ > 0 : L* non-décroissant en σ (la dérive positive domine à faible vol)
    for mu in [0.001, 0.002]:
        sigmas = [0.03, 0.06, 0.12, 0.24]
        Ls = [max_leverage_for_alpha(0.10, 0.02, mu, s) for s in sigmas]
        assert all(b >= a - 1e-6 for a, b in zip(Ls, Ls[1:])), (mu, Ls)


def test_max_leverage_croit_en_derive_baissiere():
    # μ de plus en plus négatif (bear) → L* plus grand
    L_bear = max_leverage_for_alpha(0.10, 0.02, -0.002, 0.03)
    L_neutre = max_leverage_for_alpha(0.10, 0.02, 0.0, 0.03)
    L_bull = max_leverage_for_alpha(0.10, 0.02, 0.002, 0.03)
    assert L_bear > L_neutre > L_bull


def test_max_leverage_infeasible_en_drift_haussier_fort_vol_faible():
    # μ=+0.002, σ=0.01 : même à L→1, P(liq) > 10% → L* = ∅
    assert max_leverage_for_alpha(0.10, 0.02, 0.002, 0.01) is None


def test_max_leverage_decroit_en_espacement_tp():
    # s plus grand = TP plus loin = position exposée plus longtemps → L* plus petit
    L_small = max_leverage_for_alpha(0.10, 0.01, 0.0, 0.03)
    L_big = max_leverage_for_alpha(0.10, 0.05, 0.0, 0.03)
    assert L_small > L_big


def test_max_leverage_monotone_en_alpha():
    L1 = max_leverage_for_alpha(0.05, 0.02, 0.0005, 0.03)
    L2 = max_leverage_for_alpha(0.20, 0.02, 0.0005, 0.03)
    assert L2 > L1


def test_max_leverage_alpha_trop_strict_infeasible():
    assert max_leverage_for_alpha(1e-12, 0.02, 0.0, 0.03) is None
