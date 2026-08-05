"""
windows.py — Fenêtres glissantes INDÉPENDANTES pour H4.
===============================================================================
RATTACHEMENT : H4 (validation hors-échantillon).

  CONVENTIONS (documentées) :
    W1  Fenêtres de TEST non chevauchantes, adjacentes (pas = n_test) : chaque
        barre appartient à au plus UNE fenêtre de test → les fenêtres sont les
        unités d'indépendance du test cluster-robuste H4 (V5).
    W2  Fenêtre d'APPRENTISSAGE = [test_start − n_train, test_start) : la
        prédiction d'une fenêtre de test n'utilise QUE des données antérieures.
    W3  Une position est attribuée à la fenêtre de test où elle s'OUVRE ; elle
        est suivie jusqu'à sa résolution (TP ou liq), même au-delà de la
        fenêtre. Positions ouvertes à la toute fin du jeu (jamais résolues) :
        censurées, comptées à part.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class Window:
    id: int
    train_start: int      # inclusif
    train_end: int        # exclusif
    test_start: int       # inclusif
    test_end: int         # exclusif


def build_windows(n_total: int, n_train: int, n_test: int) -> List[Window]:
    """W1–W2 : fenêtres de test adjacentes non chevauchantes, train précédent."""
    if n_train <= 0 or n_test <= 0:
        raise ValueError("n_train et n_test doivent être > 0.")
    if n_train + n_test > n_total:
        raise ValueError(
            f"Jeu trop court : {n_total} barres < n_train + n_test "
            f"= {n_train + n_test}."
        )

    windows: List[Window] = []
    wid = 0
    test_start = n_train
    while test_start + n_test <= n_total:
        windows.append(Window(
            id=wid,
            train_start=test_start - n_train,
            train_end=test_start,
            test_start=test_start,
            test_end=test_start + n_test,
        ))
        wid += 1
        test_start += n_test
    return windows


def tag_opening_indices(indices: Sequence[int], windows: Sequence[Window]) -> List[int]:
    """W3 : fenêtre d'appartenance d'une position (par index de barre d'ouverture).

    Retourne l'id de fenêtre, ou −1 si la position s'ouvre hors de toute
    fenêtre de test (train initial / queue non couverte).
    """
    out: List[int] = []
    for idx in indices:
        wid = -1
        for w in windows:
            if w.test_start <= idx < w.test_end:
                wid = w.id
                break
        out.append(wid)
    return out
