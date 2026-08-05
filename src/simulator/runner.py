"""
runner.py — Boucle de backtest (J4).
===============================================================================
RATTACHEMENT : H5 (accounting), agrège barres + funding + stratégie + moteur.

  RÈGLES DE BOUCLE (documentées) :
    R1  Ordre par barre : 1) moteur `on_bar` (funding → liq → TP) pour les
        positions EXISTANTES ; 2) décisions de la stratégie sur cette barre →
        ouvertures au close (G3). Une position ouverte à la clôture de la barre
        t n'est donc contrôlée qu'à partir de t+1 : aucun monitoring partiel ni
        lookahead sur sa barre d'ouverture.
    R2  POLICY DE SKIP (aucune exception avalée) : un signal non exécutable
        est compté (n_skipped_cash / n_skipped_cap) et ignoré, le run se
        poursuit. C'est une décision DOCUMENTÉE du backtest, pas un crash
        silencieux du moteur (E9).
    R3  `max_positions` plafonne le nombre de positions simultanées ; au-delà,
        les signaux sont comptés n_skipped_max_pos.
    R4  Le funding_rate vient de `funding_map` (Series indexée par ts de
        barre, alignée par funding_map_for_hourly_bars). ts absent → 0.
    R5  RESIZE (pas de biais de sélection) : si le notionnel du signal dépasse
        le cap ou la marge+frais le cash disponible, la TAILLE qty est réduite
        (jamais la géométrie L/s) pour être exécutable ; skip uniquement si la
        qty résultante est nulle. Les barrières liq/TP ne dépendent que de L et
        de s — la taille n'affecte PAS la thèse (H4). Compté n_skipped_cash/cap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from src.simulator.engine import Bar, OpenSignal, SimulationEngine
from src.strategy.grid_short import ShortGridStrategy


@dataclass
class RunConfig:
    initial_capital: float = 10_000.0
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    slip_bps: float = 0.0
    notional_cap: float = 49_000.0
    max_positions: Optional[int] = None


@dataclass
class RunResult:
    engine: SimulationEngine
    n_signals: int
    n_opened: int
    n_skipped_cash: int
    n_skipped_cap: int
    n_skipped_max_pos: int

    def __post_init__(self) -> None:
        assert (
            self.n_signals
            == self.n_opened
            + self.n_skipped_cash
            + self.n_skipped_cap
            + self.n_skipped_max_pos
        ), "La somme des issues des signaux ne correspond pas (R2)."


def _resize_signal(engine: SimulationEngine, cfg: RunConfig, sig: OpenSignal,
                   mark: float) -> tuple[Optional[OpenSignal], Optional[str]]:
    """R5 : réduit qty (jamais L/s) pour rendre le signal exécutable.

    Retourne (signal_redimensionné, None) ou (None, raison) si impossible.
    """
    entry = mark * (1.0 - cfg.slip_bps / 10_000)
    if entry <= 0.0:
        return None, "notional_cap"
    max_notional = cfg.notional_cap * (1.0 - 1e-12)   # garde-fou flottant
    per_unit = entry * (1.0 / sig.leverage + cfg.maker_fee)   # marge + frais par SOL
    qty_max = min(sig.qty, max_notional / entry)
    if engine.cash_usd > 0.0:
        qty_max = min(qty_max, engine.cash_usd * 0.995 / per_unit)
    if qty_max <= 1e-12:
        return None, "cash"
    if qty_max >= sig.qty:
        return sig, None
    return OpenSignal(qty=qty_max, leverage=sig.leverage, tp_distance=sig.tp_distance), None


def run_backtest(
    bars: List[Bar],
    strategy: ShortGridStrategy,
    funding_map: Optional[pd.Series] = None,
    cfg: Optional[RunConfig] = None,
) -> RunResult:
    cfg = cfg or RunConfig()
    engine = SimulationEngine(
        cfg.initial_capital,
        maker_fee=cfg.maker_fee,
        taker_fee=cfg.taker_fee,
        slip_bps=cfg.slip_bps,
        notional_cap=cfg.notional_cap,
    )

    n_signals = n_opened = 0
    n_skip_cash = n_skip_cap = n_skip_max = 0

    for bar in bars:
        rate = None
        if funding_map is not None:
            rate = funding_map.get(bar.ts)

        engine.on_bar(bar, funding_rate=rate)

        for mark, sig in strategy.on_bar(bar):
            n_signals += 1
            sig, reason = _resize_signal(engine, cfg, sig, mark)
            if sig is None:
                if reason == "cash":
                    n_skip_cash += 1
                elif reason == "notional_cap":
                    n_skip_cap += 1
                else:  # pragma: no cover
                    raise AssertionError(f"Raison inattendue : {reason}")
                continue
            if cfg.max_positions is not None and len(engine.positions) >= cfg.max_positions:
                n_skip_max += 1
                continue
            engine.open_short(sig, mark, bar.ts)
            n_opened += 1

    return RunResult(
        engine=engine,
        n_signals=n_signals,
        n_opened=n_opened,
        n_skipped_cash=n_skip_cash,
        n_skipped_cap=n_skip_cap,
        n_skipped_max_pos=n_skip_max,
    )
