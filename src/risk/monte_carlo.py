"""
monte_carlo.py — Vérité terrain GBM (H2).
===============================================================================
RATTACHEMENT : H2 (ancre anti-contradiction).

  Simule un log-prix en mouvement brownien arithmétique X_t = X_0 + μt + σW_t
  en pas discret dt, avec barrières absorbantes à +b (liquidation, HAUTE) et
  −a (take-profit, BASSE). Compte quelle barrière est touchée en premier.

  CONVENTIONS (documentées) :
    C1  Détection par CROISEMENT du pas discret (X ≥ b / X ≤ −a). Le pas fin
        (dt ≤ 0.01 h) rend le biais de discrétisation négligeable devant la
        tolérance binomiale 5σ du test.
    C2  `cap` : nombre maximal de pas par trajectoire. Au-delà, la trajectoire
        est marquée "indécise" (compter la fréquence : doit être ~0). Le
        brownien 1D touche l'une des barrières presque sûrement, mais un cap
        borné est nécessaire.
    C3  Résultat : vecteur d'entiers 0=indécise, 1=liquidée (+b), 2=TP (−a).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.risk.two_barriers import _prob_from_ab


@dataclass(frozen=True)
class GroundTruth:
    n: int
    n_liquidated: int
    n_take_profit: int
    n_undecided: int
    p_hat: float          # fréquence observée de liquidation
    p_pred: float         # P(liq) prédite (H2)
    max_error_5sigma: float  # 5·√(P(1−P)/N) : tolérance du test

    def passes(self) -> bool:
        """Critère H2 : |p̂ − P| ≤ 5·√(P(1−P)/N)."""
        return abs(self.p_hat - self.p_pred) <= self.max_error_5sigma


def simulate_two_barrier(
    mu: float,
    sigma: float,
    a: float,
    b: float,
    n: int,
    dt: float = 0.01,
    cap: int = 200_000,
    seed: int = 42,
) -> GroundTruth:
    """Monte Carlo du premier passage à deux barrières (C1–C3).

    Processus CONTINU approché : pas fin dt, détection par croisement du pas
    discret. C'est la vérité terrain de H2 (monitoring continu).
    """
    if sigma <= 0.0:
        raise ValueError("sigma doit être > 0.")
    if a <= 0.0 or b <= 0.0:
        raise ValueError(f"a, b > 0 requis : a={a}, b={b}")
    if n <= 0 or dt <= 0.0 or cap <= 0:
        raise ValueError("n, dt, cap doivent être > 0.")

    rng = np.random.default_rng(seed)
    X = np.zeros(n, dtype=float)
    done = np.zeros(n, dtype=bool)
    result = np.zeros(n, dtype=np.int8)

    step_mu = mu * dt
    step_sigma = sigma * np.sqrt(dt)

    for _ in range(cap):
        active = ~done
        if not active.any():
            break
        X[active] += step_mu + step_sigma * rng.standard_normal(int(active.sum()))

        up = active & (X >= b)
        down = active & (X <= -a)
        result[up] = 1
        result[down] = 2
        done[up | down] = True

    n_und = int((result == 0).sum())
    n_liq = int((result == 1).sum())
    n_tp = n - n_liq - n_und

    p_pred = _prob_from_ab(a, b, mu, sigma)
    p_hat = n_liq / n
    tol = 5.0 * np.sqrt(p_pred * (1.0 - p_pred) / n)

    return GroundTruth(
        n=n,
        n_liquidated=n_liq,
        n_take_profit=n_tp,
        n_undecided=n_und,
        p_hat=float(p_hat),
        p_pred=float(p_pred),
        max_error_5sigma=float(tol),
    )


def simulate_two_barrier_bars(
    mu: float,
    sigma: float,
    a: float,
    b: float,
    n: int,
    steps_per_hour: int = 30,
    cap: int = 200_000,
    seed: int = 42,
) -> GroundTruth:
    """Monte Carlo du premier passage à deux barrières SOUS MONITORING BARRE.

    Sémantiques EXACTES du moteur (engine.py E6 + barre OHLC) :
      - une barre = un rendement log delta ~ N(μ, σ) + un pont brownien
        intra-barre simulé en `steps_per_hour` sous-pas (mêmes extrêmes
        high/low que le générateur OHLC `generate_gbm_hourly_ohlc`) ;
      - liquidation si `X + max_barre ≥ b`, SINON take-profit si
        `X + min_barre ≤ −a` (la liq gagne en cas de double touch, E6) ;
      - X est le log-écart cumulé depuis l'entrée.

    C'est la prédiction adaptée au SIMULATEUR (H4) : la formule continue H2
    ignore le biais de granularité du monitoring horaire, que cette fonction
    intègre. À (μ, σ) fixes, P converge vers la valeur continue quand
    `steps_per_hour → ∞`.
    """
    if sigma <= 0.0:
        raise ValueError("sigma doit être > 0.")
    if a <= 0.0 or b <= 0.0:
        raise ValueError(f"a, b > 0 requis : a={a}, b={b}")
    if n <= 0 or steps_per_hour < 1 or cap <= 0:
        raise ValueError("n, steps_per_hour, cap doivent être ≥ 1.")

    rng = np.random.default_rng(seed)
    X = np.zeros(n, dtype=float)
    done = np.zeros(n, dtype=bool)
    result = np.zeros(n, dtype=np.int8)

    m = steps_per_hour
    # bridge : U construit par cumsum de N(0, 1/√m) => Var(U_j) = j/m, donc
    # bridge = U − (j/m)·U_m est un PONT STANDARD (Var = (j/m)(1−j/m)).
    # logpath = (j/m)·Δ + σ·bridge a bien la covariance d'un mouvement
    # brownien discret (Var = σ²·(j/m)). (Erreur corrigée J6 : NE PAS rescale
    # par σ/√m, ce qui divisait la variance intra-barre par m.)

    for _ in range(cap):
        active = ~done
        cnt = int(active.sum())
        if cnt == 0:
            break

        delta = rng.normal(mu, sigma, cnt)
        # pont brownien intra-barre : u_j ~ N(0, 1/m), U_m ~ N(0,1) ≡ W(1)
        u = rng.normal(0.0, 1.0 / np.sqrt(m), (cnt, m))
        U = np.cumsum(u, axis=1)
        bridge = U - (np.arange(1, m + 1) / m)[None, :] * U[:, -1:]
        logpath = (delta[:, None] * (np.arange(1, m + 1) / m)[None, :]) + sigma * bridge
        bar_max = logpath.max(axis=1)
        bar_min = logpath.min(axis=1)

        idx = np.nonzero(active)[0]
        Xa = X[idx]
        liq = Xa + bar_max >= b
        tp = ~liq & (Xa + bar_min <= -a)
        result[idx[liq]] = 1
        result[idx[tp]] = 2
        done[idx[liq | tp]] = True
        X[idx[~liq & ~tp]] += delta[~liq & ~tp]

    n_und = int((result == 0).sum())
    n_liq = int((result == 1).sum())
    n_tp = n - n_liq - n_und

    p_hat = n_liq / n
    return GroundTruth(
        n=n,
        n_liquidated=n_liq,
        n_take_profit=n_tp,
        n_undecided=n_und,
        p_hat=float(p_hat),
        p_pred=float("nan"),
        max_error_5sigma=float("nan"),
    )
