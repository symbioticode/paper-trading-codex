"""
engine.py — Moteur d'exécution simulé (marge isolée, accounting USD).
================================================================================
RATTACHEMENT : H5 (cohérence du numéraire), support de H4.

  Ce module sépare STRICTEMENT :
    - l'exécution (quand/à quel prix une position ouvre, ferme, se liquide) ;
    - la comptabilité (cash / marges / PnL en USD).

  CONVENTIONS (documentées, aucune silencieuse — producteur §8) :
    E1  Accounting 100% en USD. `cash_usd` est l'argent disponible ; la valeur
        du portefeuille est `equity_usd = cash + Σ marges + Σ PnL non réalisé`.
    E2  Marge isolée par position : `margin = notional / L`.
    E3  À l'ouverture, la marge et les frais maker sont débités du cash.
    E4  À la fermeture, la marge est restituée et le PnL réalisé est crédité.
    E5  LIQUIDATION : la position perd l'intégralité de sa marge (PnL réalisé
        = −margin + funding net). ASSUME : la marge de maintenance résiduelle
        est négligée (de l'ordre de MMR·notional). Vérification cible : compte
        démo réel.
    E6  Ordre dans une barre : liquidation (touch sur high) AVANT take-profit
        (touch sur low). Si les deux se touchent, la liq gagne (conservateur).
    E7  Funding : pour un SHORT, funding_rate > 0 ⇒ shorts REÇOIVENT
        (les longs paient). PnL funding = rate × notionnel courant.
        Marque = close de la barre (ASSUME, vérification : prix index).
    E8  Slippage paramétrique (bps) : entrée short = close·(1 − slip),
        sortie = prix cible·(1 + slip). Liquidation non affectée.
        ASSUME : slip constant, indépendant de la taille (vérif. : marché).
    E9  Aucune exception avalée : tout appel au moteur qui reçoit un signal
        invalide lève une erreur explicite.

  Toute position ouverte est un SHORT (le projet est un grid SHORT).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np
import pandas as pd

from src.market.exchange_spec import liquidation_price_short


@dataclass
class Bar:
    ts: pd.Timestamp
    open: float
    high: float
    low: float
    close: float


@dataclass
class Position:
    entry: float
    qty: float
    leverage: float
    notional: float
    margin: float
    liq_price: float
    tp_price: float
    opened_at: pd.Timestamp
    entry_fee: float
    funding: float = 0.0

    def unrealized(self, price: float) -> float:
        """DEDUCE : PnL non réalisé d'un SHORT = (entry − prix)·qty·L."""
        return (self.entry - price) * self.qty * self.leverage


@dataclass
class Trade:
    opened_at: pd.Timestamp
    closed_at: pd.Timestamp
    entry: float
    exit: float
    qty: float
    leverage: float
    gross_pnl: float
    entry_fee: float
    exit_fee: float
    funding: float
    net_pnl: float
    reason: str


@dataclass
class OpenSignal:
    """Décision d'ouverture émise par la stratégie (J4). Champs valides :
    entry_price (marque), qty (SOL), leverage, tp_distance (fraction)."""

    qty: float
    leverage: float
    tp_distance: float


@dataclass
class EngineState:
    ts: pd.Timestamp
    close: float
    cash_usd: float
    equity_usd: float
    n_positions: int
    liquidations: int


class SimulationEngine:
    def __init__(
        self,
        initial_capital: float,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0004,
        slip_bps: float = 0.0,
        notional_cap: float = 49_000.0,
    ):
        self.initial_capital = float(initial_capital)
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slip_bps = slip_bps
        self.notional_cap = notional_cap

        self.cash_usd = float(initial_capital)
        self.positions: List[Position] = []
        self.trades: List[Trade] = []
        self.liquidations = 0
        self.history: List[EngineState] = []

    # ─── API publique ────────────────────────────────────────────────────────

    def on_bar(self, bar: Bar, funding_rate: Optional[float] = None) -> None:
        """Traite une barre : funding → liq (high) → TP (low) → (l'ouverture est
        faite par la stratégie AVANT l'appel via open_signal)."""
        self._apply_funding(funding_rate)

        for pos in list(self.positions):
            if bar.high >= pos.liq_price:
                self._liquidate(pos, bar)

        for pos in list(self.positions):
            if bar.low <= pos.tp_price:
                # E8 : slippage sur la sortie TP (ordre marché de rachat) :
                # exit = tp_price·(1 + slip). Corrigé REV1 (le TP ne se fermait
                # pas avec le slippage malgré E8 — surestimait le PnL net).
                exit_price = pos.tp_price * (1.0 + self.slip_bps / 10_000)
                self._close(pos, exit_price=exit_price, bar=bar, reason="take_profit")

        self.history.append(self.state(bar))

    def can_open(self, signal: OpenSignal, mark: float) -> tuple[bool, str]:
        """Teste la faisabilité d'une ouverture sans la réaliser (runner J4).

        Retourne (True, "ok") ou (False, "cash" | "notional_cap"). Doublon
        volontaire des garde-fous de `open_short`, pour que le runner puisse
        appliquer sa policy de skip SANS avaler d'exception du moteur.
        """
        entry = mark * (1.0 - self.slip_bps / 10_000)
        notional = signal.qty * entry
        if notional > self.notional_cap:
            return False, "notional_cap"
        margin = notional / signal.leverage
        entry_fee = notional * self.maker_fee
        if margin + entry_fee > self.cash_usd:
            return False, "cash"
        return True, "ok"

    def open_short(
        self,
        signal: OpenSignal,
        mark: float,
        ts: pd.Timestamp,
    ) -> Position:
        """Ouvre un SHORT à `mark` (marque de la barre) avec slippage.

        DEDUCE : entry = mark·(1 − slip) pour un vendeur.
        """
        if signal.qty <= 0 or signal.leverage <= 1.0 or signal.tp_distance <= 0:
            raise ValueError(f"Signal invalide : {signal}")

        entry = mark * (1.0 - self.slip_bps / 10_000)
        notional = signal.qty * entry
        if notional > self.notional_cap:
            raise ValueError(
                f"Notionnel {notional:.0f} > cap {self.notional_cap:.0f} — "
                "hors de la tranche de MMR documentée (changer notional_cap)."
            )

        margin = notional / signal.leverage
        entry_fee = notional * self.maker_fee
        if margin + entry_fee > self.cash_usd:
            raise ValueError(
                f"Cash insuffisant : besoin {margin + entry_fee:.2f} USD, "
                f"disponible {self.cash_usd:.2f} USD."
            )

        # AXIOME H5 : le cash est débité de (marge + frais d'entrée) ici, et le
        # PnL net du trade (net_pnl) soustrait les frais d'entrée UNE SEULE fois
        # (à la clôture). Sinon double comptage.
        self.cash_usd -= margin + entry_fee

        liq_price = liquidation_price_short(entry, signal.leverage, notional)
        pos = Position(
            entry=entry,
            qty=signal.qty,
            leverage=signal.leverage,
            notional=notional,
            margin=margin,
            liq_price=liq_price,
            tp_price=entry * (1.0 - signal.tp_distance),
            opened_at=ts,
            entry_fee=entry_fee,
        )
        self.positions.append(pos)
        return pos

    def equity_usd(self, mark: Optional[float] = None) -> float:
        """Valeur du portefeuille en USD (E1).

        DEDUCE : cash + Σ marges + Σ PnL non réalisé (marque = dernier close).
        """
        unreal = sum(p.unrealized(mark) for p in self.positions) if mark else 0.0
        margins = sum(p.margin for p in self.positions)
        return self.cash_usd + margins + unreal

    def state(self, bar: Bar) -> EngineState:
        return EngineState(
            ts=bar.ts,
            close=bar.close,
            cash_usd=self.cash_usd,
            equity_usd=self.equity_usd(mark=bar.close),
            n_positions=len(self.positions),
            liquidations=self.liquidations,
        )

    # ─── Internes ────────────────────────────────────────────────────────────

    def _apply_funding(self, rate: Optional[float]) -> None:
        if rate is None or rate == 0.0:
            return
        for pos in self.positions:
            # E7 : SHORT reçoit rate×notionnel quand rate>0.
            pos.funding += rate * pos.notional

    def _close(self, pos: Position, exit_price: float, bar: Bar, reason: str) -> Trade:
        exit_fee = pos.notional * self.taker_fee
        gross = pos.unrealized(exit_price)          # (entry − exit)·qty·L
        delta_cash = gross - exit_fee + pos.funding
        net = delta_cash - pos.entry_fee

        # Cash : restitution de la marge + delta réalisé (la fraise d'entrée a
        # déjà été débitée à l'ouverture ; elle n'apparaît ici que dans `net`).
        self.cash_usd += pos.margin + delta_cash
        self.positions.remove(pos)

        trade = Trade(
            opened_at=pos.opened_at,
            closed_at=bar.ts,
            entry=pos.entry,
            exit=exit_price,
            qty=pos.qty,
            leverage=pos.leverage,
            gross_pnl=gross,
            entry_fee=pos.entry_fee,
            exit_fee=exit_fee,
            funding=pos.funding,
            net_pnl=net,
            reason=reason,
        )
        self.trades.append(trade)
        return trade

    def _liquidate(self, pos: Position, bar: Bar) -> Trade:
        self.liquidations += 1
        # E5 : PnL réalisé = −marge (maint. négligée) + funding net ; la fraise
        # d'entrée est débitée une fois (via net).
        delta_cash = -pos.margin + pos.funding
        self.cash_usd += pos.margin + delta_cash
        self.positions.remove(pos)
        trade = Trade(
            opened_at=pos.opened_at,
            closed_at=bar.ts,
            entry=pos.entry,
            exit=pos.liq_price,
            qty=pos.qty,
            leverage=pos.leverage,
            gross_pnl=-pos.margin,
            entry_fee=pos.entry_fee,
            exit_fee=0.0,
            funding=pos.funding,
            net_pnl=delta_cash - pos.entry_fee,
            reason="liquidation",
        )
        self.trades.append(trade)
        return trade


def bars_from_frame(df: pd.DataFrame) -> List[Bar]:
    """Convertit un DataFrame OHLCV canonique en liste de Bar.

    INFER : colonnes open/high/low/close attendues. Toute colonne manquante
    lève une erreur explicite.
    """
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            raise ValueError(f"Colonne manquante : {col}")
    return [
        Bar(
            ts=idx,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
        )
        for idx, row in df.iterrows()
    ]
