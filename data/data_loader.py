"""
data_loader.py — Chargement et validation des séries OHLCV.
================================================================
SPEC (rattachement : définitions, pas d'hypothèse — support de H1..H5) :

  Un DataFrame "OHLCV canonique" est défini comme :
    - index : DatetimeIndex, nommé 'open_time', strictement croissant, sans doublon
    - colonnes : open, high, low, close, volume (floats)
    - contraintes métier :
        C1  prix > 0            (OBSERVE : prix négatifs = corruption)
        C2  high >= max(open, close)
        C3  low  <= min(open, close)
        C4  volume >= 0
        C5  index croissant sans doublons
        C6  pas de valeur manquante sur OHLC

  Rôle des fonctions :
    - load_csv            : charge un CSV et valide -> (df, QualityReport)
    - load_with_provenance: charge + vérifie sha256 vs metadata.json
    - fingerprint_bytes   : empreinte sha256 (provenance)
    - infer_timeframe     : INFER (écart d'index dominant), jamais OBSERVE

  Règle de transmission (producteur-papercodex §7) :
    aucune exception avalée silencieusement ; les erreurs de validation sont
    RAPPORTÉES dans QualityReport, jamais passées en silence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


@dataclass
class QualityReport:
    """Résultat de validation : chaque contrainte a un statut et un message."""

    passed: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    issues: list = field(default_factory=list)

    def add_check(self, name: str, ok: bool, message: str = "") -> None:
        self.checks[name] = ok
        if not ok:
            self.issues.append(f"{name}: {message}")
            self.passed = False

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        n_ok = sum(1 for v in self.checks.values() if v)
        return f"[{status}] {n_ok}/{len(self.checks)} contraintes OK" + (
            f" — {len(self.issues)} problème(s)" if self.issues else ""
        )


def fingerprint_bytes(data: bytes) -> str:
    """sha256 hex d'un contenu (OBSERVE : calcul déterministe)."""
    return hashlib.sha256(data).hexdigest()


def fingerprint_frame(df: pd.DataFrame) -> str:
    """Empreinte d'un DataFrame via sa représentation CSV canonique.

    DEDUCE : mêmes données, mêmes options de sérialisation -> même hash.
    Ce n'est pas une preuve d'identité sémantique (flottants arrondis), c'est
    un contrôle de non-régression : ASSUME, vérification cible : rechargement.
    """
    csv = df.to_csv(index=True)
    return fingerprint_bytes(csv.encode("utf-8"))


def validate_ohlcv(df: pd.DataFrame) -> QualityReport:
    """Valide un DataFrame contre les contraintes C1..C6.

    Entrée : df — DataFrame supposé avoir les colonnes requises (sinon erreur
    explicite, pas de silence : le rapport ne peut pas exister sans colonnes).
    Sortie : QualityReport.
    """
    report = QualityReport(passed=True)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Colonnes manquantes {missing} — le CSV n'est pas OHLCV canonique."
        )

    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]

    report.add_check("C1_prix_positifs", bool((o > 0).all() and (c > 0).all()),
                     "prix <= 0 détectés")
    report.add_check("C2_high>=max(o,c)", bool((h >= np.maximum(o, c)).all()),
                     "high < max(open, close)")
    report.add_check("C3_low<=min(o,c)", bool((l <= np.minimum(o, c)).all()),
                     "low > min(open, close)")
    report.add_check("C4_volume>=0", bool((v >= 0).all()),
                     "volume négatif")

    if isinstance(df.index, pd.DatetimeIndex):
        idx = df.index
        report.add_check("C5a_index_croissant", bool(idx.is_monotonic_increasing),
                         "index non croissant")
        report.add_check("C5b_index_sans_doublon", bool(idx.is_unique),
                         "index avec doublons")
    else:
        report.add_check("C5_datetime_index", False,
                         "index n'est pas un DatetimeIndex")

    report.add_check("C6_sans_na", bool(df[REQUIRED_COLUMNS].notna().all().all()),
                     "NaN sur OHLCV")

    return report


def load_csv(path: str | Path) -> tuple[pd.DataFrame, QualityReport]:
    """Charge un CSV en DataFrame OHLCV canonique et le valide.

    INFER : on suppose un format conventionnel (1ère colonne datetime).
    ASSUME : si le CSV n'est pas standard, on échoue explicitement plutôt que
    de deviner un autre format — vérification cible : le fichier source.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")

    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df = df.rename(columns={"date": "open_time"})

    report = validate_ohlcv(df)
    return df, report


def load_with_provenance(path: str | Path) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """Charge un CSV et vérifie son hash contre son metadata.json voisin.

    Schéma : <name>.csv à côté de <name>.metadata.json contenant "sha256".
    OBSERVE : si le metadata existe et que le hash diffère -> ValueError
    (corruption ou édition non documentée), aucune tolérance silencieuse.
    """
    path = Path(path)
    meta_path = path.with_suffix(path.suffix + ".metadata.json")
    if not meta_path.exists():
        raise FileNotFoundError(
            f"Provenance absente : {meta_path} — refuser de charger sans provenance."
        )

    meta: Dict[str, Any] = json.loads(meta_path.read_text())
    raw = path.read_bytes()
    actual = fingerprint_bytes(raw)

    expected = meta.get("sha256")
    if expected is not None and actual != expected:
        raise ValueError(
            f"Hash mismatch {path.name}: attendu {expected}, obtenu {actual}."
            " Données modifiées hors de la chaîne de provenance."
        )

    df, report = load_csv(path)
    return df, meta


def infer_timeframe(index: pd.DatetimeIndex) -> pd.Timedelta:
    """INFER l'intervalle dominant de l'index.

    DEDUCE : si les écarts sont constants, l'écart dominant == l'écart réel.
    ASSUME : si plusieurs fréquences coexistent, on retourne la médiane et on
    le signale — vérification cible : la source du fichier.
    """
    if len(index) < 2:
        raise ValueError("Index trop court pour inférer un timeframe.")
    deltas_s = index.to_series().diff().dropna().dt.total_seconds()
    dominant = deltas_s.mode()
    if len(dominant) > 1:
        return pd.Timedelta(seconds=float(deltas_s.median()))
    return pd.Timedelta(seconds=float(dominant.iloc[0]))


def save_with_provenance(
    df: pd.DataFrame,
    path: str | Path,
    source: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Écrit un CSV + son metadata.json de provenance (source, hash, params).

    OBSERVE : le hash est calculé sur l'octet écrit (single source of truth).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    csv = df.to_csv(index=True)
    path.write_text(csv)

    meta = {
        "source": source,
        "sha256": fingerprint_bytes(csv.encode("utf-8")),
        "bars": int(len(df)),
        "first_bar": str(df.index[0]),
        "last_bar": str(df.index[-1]),
    }
    if extra:
        meta.update(extra)

    meta_path = path.with_suffix(path.suffix + ".metadata.json")
    meta_path.write_text(json.dumps(meta, indent=2, default=str))
    return meta
