"""
Tests de la couche données — écrits depuis la SPEC (data_loader.py), pas depuis
le code. Rattachés : définitions C1..C6 + provenance (support de H1..H5).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from data.data_loader import (
    fingerprint_bytes,
    fingerprint_frame,
    infer_timeframe,
    load_csv,
    load_with_provenance,
    save_with_provenance,
    validate_ohlcv,
)


def make_ohlcv(close: list[float] | np.ndarray, start="2020-01-01", freq="h") -> pd.DataFrame:
    close = np.asarray(close, dtype=float)
    idx = pd.date_range(start, periods=len(close), freq=freq, tz="UTC")
    df = pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(len(close), 1e6),
        },
        index=idx,
    )
    df.index.name = "open_time"
    return df


# ─── C1..C6 : chaque violation doit être détectée ───────────────────────────

def test_df_canonique_passe_toutes_les_contraintes():
    df = make_ohlcv([100.0, 101.0, 100.5])
    report = validate_ohlcv(df)
    assert report.passed, report.summary()


def test_prix_negatifs_echouent():
    df = make_ohlcv([100.0, -5.0, 100.0])
    assert not validate_ohlcv(df).passed
    assert not validate_ohlcv(df).checks["C1_prix_positifs"]


def test_high_inferieur_a_close_echoue():
    df = make_ohlcv([100.0, 101.0])
    df.loc[df.index[0], "high"] = 99.0
    report = validate_ohlcv(df)
    assert not report.passed
    assert not report.checks["C2_high>=max(o,c)"]


def test_low_superieur_a_open_echoue():
    df = make_ohlcv([100.0, 101.0])
    df.loc[df.index[0], "low"] = 100.5
    report = validate_ohlcv(df)
    assert not report.passed
    assert not report.checks["C3_low<=min(o,c)"]


def test_volume_negatif_echoue():
    df = make_ohlcv([100.0])
    df.loc[df.index[0], "volume"] = -1.0
    assert not validate_ohlcv(df).checks["C4_volume>=0"]


def test_index_non_croissant_echoue():
    df = make_ohlcv([100.0, 101.0, 102.0])
    df = df.iloc[::-1]
    report = validate_ohlcv(df)
    assert not report.checks["C5a_index_croissant"]


def test_index_doublon_echoue():
    df = make_ohlcv([100.0, 101.0, 102.0])
    df = pd.concat([df, df.iloc[[0]]])
    assert not validate_ohlcv(df).checks["C5b_index_sans_doublon"]


def test_na_sur_ohlcv_echoue():
    df = make_ohlcv([100.0, 101.0])
    df.loc[df.index[0], "close"] = np.nan
    assert not validate_ohlcv(df).checks["C6_sans_na"]


def test_colonnes_manquantes_levent_erreur_explicite():
    df = make_ohlcv([100.0]).drop(columns=["volume"])
    with pytest.raises(ValueError, match="Colonnes manquantes"):
        validate_ohlcv(df)


# ─── Fingerprint / provenance ───────────────────────────────────────────────

def test_fingerprint_bytes_stable():
    assert fingerprint_bytes(b"abc") == fingerprint_bytes(b"abc")
    assert fingerprint_bytes(b"abc") != fingerprint_bytes(b"abd")


def test_fingerprint_frame_stable_et_different():
    a = make_ohlcv([100.0, 101.0])
    b = make_ohlcv([100.0, 102.0])
    assert fingerprint_frame(a) == fingerprint_frame(a)
    assert fingerprint_frame(a) != fingerprint_frame(b)


def test_roundtrip_provenance(tmp_path):
    df = make_ohlcv([100.0, 101.0, 100.5, 99.0])
    csv = tmp_path / "s.csv"
    meta = save_with_provenance(df, csv, source="test")
    assert "sha256" in meta and "bars" in meta and meta["bars"] == 4

    loaded, loaded_meta = load_with_provenance(csv)
    assert loaded_meta["sha256"] == meta["sha256"]
    assert len(loaded) == 4
    report = validate_ohlcv(loaded)
    assert report.passed, report.summary()


def test_provenance_refuse_le_hash_different(tmp_path):
    df = make_ohlcv([100.0, 101.0])
    csv = tmp_path / "s.csv"
    save_with_provenance(df, csv, source="test")

    tampered = df.copy()
    tampered.loc[tampered.index[0], "close"] = 999.0
    csv.write_text(tampered.to_csv(index=True))

    with pytest.raises(ValueError, match="Hash mismatch"):
        load_with_provenance(csv)


def test_chargement_sans_provenance_est_refuse(tmp_path):
    csv = tmp_path / "s.csv"
    make_ohlcv([100.0]).to_csv(csv)
    with pytest.raises(FileNotFoundError, match="Provenance absente"):
        load_with_provenance(csv)


# ─── infer_timeframe ────────────────────────────────────────────────────────

def test_infer_timeframe_constant():
    idx = pd.date_range("2020-01-01", periods=5, freq="h", tz="UTC")
    assert infer_timeframe(idx) == pd.Timedelta(hours=1)


def test_infer_timeframe_melange_donne_mediane():
    base = pd.date_range("2020-01-01", periods=6, freq="h", tz="UTC")
    extra = [base[-1] + pd.Timedelta(minutes=30)]
    idx = base.append(pd.DatetimeIndex(extra))
    # écarts : 1h,1h,1h,1h,0.5h,0.5h -> médiane 1h
    assert infer_timeframe(idx) == pd.Timedelta(hours=1)
