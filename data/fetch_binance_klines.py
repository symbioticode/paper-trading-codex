"""
fetch_binance_klines.py — Téléchargeur de klines Binance USDT-M avec provenance.
================================================================================
SPEC (rattachement : support de H1..H5 — fournir des données réelles dont
l'origine est vérifiable, jamais présentées comme autre chose que ce qu'elles
sont).

  Source       : Binance Futures (fapi), endpoint public /fapi/v1/klines.
  Format kline : [openTime, open, high, low, close, volume, closeTime,
                  quoteVolume, trades, takerBuyBase, takerBuyQuote, ignore]
  Pagination   : max 1500 klines/requête, triées par openTime croissant.
  Rate limit   : ce endpoint coûte 5 poids/requête (inférieur à 1000),
                 on espace les requêtes (pacing) pour rester poli.

  Provenance   : chaque CSV est accompagné d'un <nom>.metadata.json
                 (schema : source, endpoint, symbol, interval, start, end,
                 bars, first_bar, last_bar, downloaded_at, sha256, producer).

  Règles :
    - aucune exception avalée : erreur réseau / HTTP non-2xx / body JSON invalide
      -> raise avec le contexte (statut, durée, endpoint).
    - un retry borné (max 5) uniquement sur 429/418/5xx, avec backoff.
    - ASSUME : les klines Binance sont OBSERVE directes (données brutes de
      l'exchange), sans retraitement — vérification cible : comparer une barre
      contre le site Binance ou un second fournisseur.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.data_loader import save_with_provenance

BASE_URL = "https://fapi.binance.com/fapi/v1"
MAX_LIMIT = 1500
PACE_SECONDS = 0.25
MAX_RETRIES = 5


def fetch_klines(
    symbol: str,
    interval: str = "1h",
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
    timeout: int = 30,
) -> pd.DataFrame:
    """Télécharge toutes les klines [start_ms, end_ms) par pagination.

    Retourne un DataFrame OHLCV canonique (voir data_loader.py).
    INFER : colonnes converties en float, openTime -> DatetimeIndex UTC.
    """
    rows: list = []
    cursor = start_ms
    while True:
        params = {"symbol": symbol, "interval": interval, "limit": MAX_LIMIT}
        if cursor is not None:
            params["startTime"] = cursor
        if end_ms is not None:
            params["endTime"] = end_ms

        data = _get_with_retry("/klines", params, timeout)

        if not data:
            break
        rows.extend(data)
        if len(data) < MAX_LIMIT:
            break
        last_open = int(data[-1][0])
        next_cursor = last_open + _interval_ms(interval)
        if end_ms is not None and next_cursor >= end_ms:
            break
        cursor = next_cursor
        time.sleep(PACE_SECONDS)

    if not rows:
        raise ValueError(f"Aucune kline retournée pour {symbol} {interval} "
                         f"[{start_ms}, {end_ms}] — plage invalide ?")

    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    df = df.drop(columns=["ignore"])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("open_time")
    for col in ["open", "high", "low", "close", "volume",
                "quote_volume", "trades", "taker_buy_base", "taker_buy_quote"]:
        df[col] = pd.to_numeric(df[col], errors="raise")

    canon = df[["open", "high", "low", "close", "volume"]]
    return canon


def _get_with_retry(endpoint: str, params: Dict, timeout: int) -> list:
    """GET public avec retry borné. Échoue bruyamment si le serveur persiste."""
    url = BASE_URL + endpoint
    last_err: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 418) or r.status_code >= 500:
                wait = min(2 ** attempt, 30)
                time.sleep(wait)
                last_err = RuntimeError(
                    f"HTTP {r.status_code} sur {endpoint} (params={params})")
                continue
            r.raise_for_status()
        except requests.RequestException as e:
            last_err = e
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(
        f"Échec persistant du GET {url} (params={params}) : {last_err}")


def _interval_ms(interval: str) -> int:
    """INFER : conversion d'un intervalle Binance en millisecondes."""
    unit = interval[-1]
    n = int(interval[:-1])
    factor = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}[unit]
    return n * factor


def _parse_time(value: str) -> int:
    """Parse 'YYYY-MM-DD[THH:MM:SS]' en ms UTC. INFER : format ISO local→UTC."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def download_to_disk(
    symbol: str,
    interval: str,
    start: str,
    end: str,
    out: str | Path,
    producer_version: str = "0.1.0",
) -> Dict:
    """Télécharge et écrit CSV + metadata de provenance. Retourne le metadata."""
    df = fetch_klines(
        symbol, interval,
        start_ms=_parse_time(start),
        end_ms=_parse_time(end),
    )
    df = df[~df.index.duplicated(keep="last")]
    meta = save_with_provenance(
        df, out,
        source=f"binance-fapi:{symbol}:{interval}",
        extra={
            "endpoint": BASE_URL + "/klines",
            "symbol": symbol,
            "interval": interval,
            "start": start,
            "end": end,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "producer": {"script": "fetch_binance_klines.py",
                         "version": producer_version},
        },
    )
    return meta


def main() -> None:
    p = argparse.ArgumentParser(description="Télécharge les klines Binance USDT-M")
    p.add_argument("--symbol", default="SOLUSDT")
    p.add_argument("--interval", default="1h")
    p.add_argument("--start", required=True, help="YYYY-MM-DD[THH:MM:SS] UTC")
    p.add_argument("--end", required=True)
    p.add_argument("--out", required=True, help="chemin du CSV de sortie")
    args = p.parse_args()

    meta = download_to_disk(
        args.symbol, args.interval, args.start, args.end, args.out)
    print(json.dumps(meta, indent=2, default=str))


if __name__ == "__main__":
    main()
