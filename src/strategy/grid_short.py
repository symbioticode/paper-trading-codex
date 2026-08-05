"""
grid_short.py — Stratégie grille SHORT pure (J4).
===============================================================================
RATTACHEMENT : H4 (fournit les positions à tester), support de H2/H3.

  La stratégie est PURE et DÉTERMINISTE : `on_bar(bar)` ne dépend que de la
  séquence de barres passées. Aucune connaissance du portefeuille, du cash ou
  des positions ouvertes : c'est le RUNNER (runner.py) qui applique la policy
  d'exécution (affordabilité, plafond de positions).

  RÈGLES DE GRILLE (documentées, aucune silencieuse — producteur §8) :
    G1  Ancre `A` = premier close (ou price passé à `reset`).
    G2  Niveaux de vente : L_i = A·(1 + i·s), i = 1..N (N = grid_size).
    G3  Signal SHORT : quand `bar.high ≥ L_i` et le niveau n'est pas déjà
        dépensé, on déclenche. EXÉCUTION au CLOSE de la barre déclenchante
        (ordre marché à la clôture, entrée = close) : c'est une CONVENTION
        nécessaire pour que l'entrée soit le prix courant et que H2 s'applique
        exactement depuis l'entrée (l'exécution au niveau introduirait un
        overshoot d'entrée — voir la correction documentée dans METHODS.md).
    G4  Chaque position a un TP à s en-dessous de son entrée
        (tp_distance = s) : la grille revend s·notional à chaque aller-retour.
    G5  Ré-anchrage (sur CLOSE) :
        - si close < A·(1 − s) : le marché a cassé la grille vers le bas → A = close ;
        - si close > A·(1 + (N+1)·s) : le marché a cassé le haut de la bande → A = close.
        Les niveaux sont reconstruits, les niveaux dépensés remis à zéro. Les
        positions DÉJÀ OUVERTES gardent leur TP (entry·(1−s)).
    G6  UNE position au plus par barre (la première marque non dépensée
        franchie) : deux positions ouvertes au même close avec les mêmes
        barrières seraient PARFAITEMENT corrélées, ce qui casserait
        l'indépendance binomiale de H4.
    G7  Un niveau dépensé n'est pas re-vendu (pas de pyramide sur la même
        marque) jusqu'au prochain ré-anchrage.

  Taille par position = qty_sol (SOL), levier = `leverage` (fixe : la thèse
  teste un L donné). Sizing fractionnaire du capital : J6 (validate_thesis).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.simulator.engine import Bar, OpenSignal


@dataclass
class GridConfig:
    grid_size: int      # N : nombre de niveaux au-dessus de l'ancre
    grid_ratio: float   # s : espacement relatif (et distance TP)
    qty_sol: float      # taille par position (SOL)
    leverage: float     # levier (fixe, > 1)

    def __post_init__(self) -> None:
        if self.grid_size < 1:
            raise ValueError(f"grid_size doit être ≥ 1 : {self.grid_size}")
        if self.grid_ratio <= 0.0:
            raise ValueError(f"grid_ratio doit être > 0 : {self.grid_ratio}")
        if self.qty_sol <= 0.0:
            raise ValueError(f"qty_sol doit être > 0 : {self.qty_sol}")
        if self.leverage <= 1.0:
            raise ValueError(f"leverage doit être > 1 : {self.leverage}")


class ShortGridStrategy:
    def __init__(self, config: GridConfig):
        self.config = config
        self.anchor: Optional[float] = None
        self.levels: List[float] = []
        self.spent: List[bool] = []

    # ─── API publique ────────────────────────────────────────────────────────

    def reset(self, price: float) -> None:
        """G1 : pose une nouvelle ancre et reconstruit la grille."""
        self.anchor = float(price)
        s = self.config.grid_ratio
        n = self.config.grid_size
        self.levels = [self.anchor * (1.0 + s * i) for i in range(1, n + 1)]
        self.spent = [False] * n

    def on_bar(self, bar: Bar) -> List[Tuple[float, OpenSignal]]:
        """Renvoie [(close, signal), ...] : au plus UN signal par barre (G6),
        exécuté au close (G3). Pure et déterministe."""
        if self.anchor is None:
            self.reset(bar.close)
        self._maybe_reanchor(bar.close)

        for i, level in enumerate(self.levels):
            if self.spent[i]:
                continue
            if bar.high >= level:
                self.spent[i] = True
                return [(
                    bar.close,
                    OpenSignal(
                        qty=self.config.qty_sol,
                        leverage=self.config.leverage,
                        tp_distance=self.config.grid_ratio,
                    ),
                )]
        return []

    # ─── Internes ────────────────────────────────────────────────────────────

    def _maybe_reanchor(self, close: float) -> None:
        """G5 : ré-ancre si le close sort de la bande [A·(1−s), A·(1+(N+1)s)]."""
        s = self.config.grid_ratio
        n = self.config.grid_size
        below = self.anchor * (1.0 - s)
        above = self.anchor * (1.0 + s * (n + 1))
        if close < below or close > above:
            self.reset(close)
