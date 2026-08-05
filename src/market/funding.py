"""
funding.py — Historique de funding Binance USDT-M (SOLUSDT).
================================================================================
RATTACHEMENT : H4/H5 (le funding affecte le PnL réel du SHORT et le drift net).

  Source : GET /fapi/v1/fundingRate (public, sans clé API).
  Série  : (fundingTime, fundingRate) — un taux toutes les 8h environ.
  Use    : le simulateur applique le funding aux barres 1h correspondantes.

  INFER  : le taux renvoyé est un taux 8h (fraction du notionnel payée/recue).
  ASSUME : pas de gap de funding sur l'historique (les trous sont signalés,
  jamais comblés silencieusement — producteur-papercodex §7).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from data.data_loader import save_with_provenance

BASE_URL = "https://fapi.binance.com/fapi/v1"
MAX_LIMIT = 1000
PACE_SECONDS = 0.25


def fetch_funding_history(
    symbol: str = "SOLUSDT",
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
    timeout: int = 30,
) -> pd.DataFrame:
    """Récupère l'historique complet de funding par pagination.

    Retourne un DataFrame indexé par fundingTime (UTC), colonne 'funding_rate'.
    """
    rows: list = []
    cursor = start_ms
    while True:
        params = {"symbol": symbol, "limit": MAX_LIMIT}
        if cursor is not None:
            params["startTime"] = cursor
        if end_ms is not None:
            params["endTime"] = end_ms

        url = BASE_URL + "/fundingRate"
        last_err = None
        data = None
        for attempt in range(5):
            try:
                r = requests.get(url, params=params, timeout=timeout)
                if r.status_code == 200:
                    data = r.json()
                    break
                if r.status_code in (429, 418) or r.status_code >= 500:
                    time.sleep(min(2 ** attempt, 30))
                    last_err = RuntimeError(f"HTTP {r.status_code} fundingRate")
                    continue
                r.raise_for_status()
            except requests.RequestException as e:
                last_err = e
                time.sleep(min(2 ** attempt, 30))
        if data is None:
            raise RuntimeError(f"Échec fundingRate : {last_err}")

        if not data:
            break
        rows.extend(data)
        if len(data) < MAX_LIMIT:
            break
        cursor = int(data[-1]["fundingTime"]) + 1
        time.sleep(PACE_SECONDS)

    if not rows:
        raise ValueError("Aucun funding récupéré — plage vide ?")

    df = pd.DataFrame(rows)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df = df.set_index("fundingTime")
    df["funding_rate"] = pd.to_numeric(df["fundingRate"], errors="raise")
    return df[["funding_rate"]].sort_index()


def load_funding_history(path: str | Path) -> pd.DataFrame:
    """Charge un CSV de funding + son hash (via data_loader.provenance)."""
    from data.data_loader import load_with_provenance
    df, meta = load_with_provenance(path)
    return df


def funding_map_for_hourly_bars(
    funding_df: pd.DataFrame,
    bars_index: pd.DatetimeIndex,
) -> pd.Series:
    """Aligne l'historique de funding sur les barres 1h.

    DEDUCE : les funding ont lieu aux heures 00/08/16 UTC (avec un décalage en
    millisecondes) ; on arrondit chaque timestamp à l'heure (floor) et on
    ne retient que les heures présentes dans l'index des barres.
    INFER : en cas de doublon intra-heure, on garde le dernier taux (ASSUME :
    les doublons sont des artefacts de re-délivrance, vérification : source).
    """
    floor = funding_df.index.floor("h")
    grouped = funding_df["funding_rate"].groupby(floor).last()
    return grouped.reindex(bars_index).dropna()


if __name__ == "__main__":
    import json
    from datetime import datetime, timezone

    out = sys.argv[1] if len(sys.argv) > 1 else "data/raw/SOLUSDT_funding.csv"
    start = sys.argv[2] if len(sys.argv) > 2 else "2020-09-01"

    start_ms = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp() * 1000)
    df = fetch_funding_history(start_ms=start_ms)
    df = df[~df.index.duplicated(keep="last")]
    meta = save_with_provenance(
        df, out,
        source="binance-fapi:fundingRate:SOLUSDT",
        extra={
            "endpoint": BASE_URL + "/fundingRate",
            "symbol": "SOLUSDT",
            "start": start,
            "interval_expected_hours": 8.0,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    print(json.dumps(meta, indent=2, default=str))
