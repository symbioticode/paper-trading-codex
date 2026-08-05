"""
exchange_spec.py — Spec Binance USDT-M (SOLUSDT) : marge, frais, liquidation.
================================================================================
RATTACHEMENT : H1 (formule de liquidation dérivée du spec).

CONTENU :
  - Table de marge de maintenance (MMR) par tranche de notionnel.
  - Frais maker/taker (VIP 0, sans rabais BNB).
  - Fonctions pures de prix de liquidation SHORT (formule exacte).
  - Fonction de distance de liquidation d(entry, L, notional).

STATUT DES VALEURS (producteur-papercodex §2/§3 — pas de seuil muet) :

  OBSERVE (source fiable) :
    - structure des tiers (notional cap croissants) : spec Binance USDT-M,
      pattern stable publié dans la doc "Risk limits".
    - les frais VIP0 de base (maker 0.02%, taker 0.04%) : page "Fees" Binance.

  ASSUME (non vérifié ici, vérification cible documentée) :
    - TIER_1_MMR = 0.0050 (0.50%) pour SOLUSDT.
      Vérification : endpoint /fapi/v1/leverageBracket?symbol=SOLUSDT (requiert
      une clé API — 401 sans clé au 2026-08-04). Le code ne prétend PAS que
      cette valeur est OBSERVE ; il la lit depuis cette constante et l'écrit
      dans la provenance des résultats.
    - pas de rabais (pas de BNB, pas de VIP).
  -> Toute analyse qui change de valeur doit re-pointer ici, jamais ailleurs.
"""

from __future__ import annotations

from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────────────────────
# Marge de maintenance — tranches SOLUSDT (USDT-M).
# ASSUME : TIER_1_MMR = 0.50%. Vérification cible : leverageBracket avec clé API.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MMRTier:
    notional_cap: float   # notionnel max de la tranche (USDT)
    mmr: float            # maintenance margin rate pour cette tranche


SOLUSDT_MMR_TIERS: tuple[MMRTier, ...] = (
    MMRTier(notional_cap=50_000,   mmr=0.0050),
    MMRTier(notional_cap=150_000,  mmr=0.0100),
    MMRTier(notional_cap=450_000,  mmr=0.0150),
    MMRTier(notional_cap=2_000_000, mmr=0.0250),
    MMRTier(notional_cap=4_000_000, mmr=0.0500),
    MMRTier(notional_cap=float("inf"), mmr=0.1000),
)

# ASSUME : VIP0 sans rabais. Vérification : page Binance "Futures fees".
MAKER_FEE = 0.0002
TAKER_FEE = 0.0004


def mmr_for_notional(notional: float) -> float:
    """DEDUCE : MMR de la tranche contenant `notional`.

    INFER : si le notionnel dépasse la dernière tranche connue, on renvoie
    celle-ci (borné supérieur de la table) — jamais extrapolé au-delà.
    """
    if notional < 0:
        raise ValueError(f"Notionnel négatif : {notional}")
    for tier in SOLUSDT_MMR_TIERS:
        if notional <= tier.notional_cap:
            return tier.mmr
    return SOLUSDT_MMR_TIERS[-1].mmr


# ─────────────────────────────────────────────────────────────────────────────
# Liquidation SHORT (H1)
# ─────────────────────────────────────────────────────────────────────────────

def liquidation_price_short(entry: float, leverage: float, notional: float) -> float:
    """H1 : prix de liquidation SHORT en marge isolée.

    Dérivation (docs/METHODS.md §3) : à la liquidation,
      marge_isolée + PnL_non_réalisé = marge_de_maintenance
      E·qty/L + (E − liq)·qty = liq·qty·MMR
      => liq = E·(1 + 1/L) / (1 + MMR)

    Cas limites DEDUCE :
      - L → ∞  : liq → E/(1+MMR) < E, ce qui est impossible pour un SHORT.
        La position ne peut pas exister si la marge initiale < marge de
        maintenance à l'entrée, soit 1/L < MMR => on fige liq = E.
      - MMR → 0 : liq → E·(1 + 1/L) (repaire).
      - L → 1 (pas de levier) : liq = E·2/(1+MMR) ≈ 2E, cohérent (le prix doit
        doubler pour perdre la totalité de la marge).
    """
    if leverage <= 1.0:
        raise ValueError(f"Levier invalide : {leverage} (doit être > 1)")
    mmr = mmr_for_notional(notional)
    if 1.0 / leverage < mmr:
        return entry
    return entry * (1.0 + 1.0 / leverage) / (1.0 + mmr)


def liquidation_distance_short(entry: float, leverage: float, notional: float) -> float:
    """Distance de liquidation au-dessus de l'entrée : d = (liq − E)/E.

    DEDUCE : dérivé de liquidation_price_short. Pour un SHORT, d > 0 est la
    hausse (fraction) que le prix peut subir avant liquidation.
    """
    liq = liquidation_price_short(entry, leverage, notional)
    return (liq - entry) / entry
