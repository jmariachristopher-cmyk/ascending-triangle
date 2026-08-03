"""
upstox_client.py
-----------------
Minimal Upstox REST wrapper for the Streamlit screener app. Unlike the
desktop project's upstox_api.py, this takes the access token as a plain
function argument instead of reading it from a local .env file — because
in a deployed Streamlit app there's no local filesystem secret to read;
the user pastes their own daily token into the app's UI each session.
"""

import urllib.parse
import requests
import pandas as pd

BASE_URL = "https://api.upstox.com"


def _headers(token: str):
    return {"Accept": "application/json", "Authorization": f"Bearer {token}"}


def _encode_key(instrument_key: str) -> str:
    return urllib.parse.quote(instrument_key, safe="")


def _candles_to_df(candles) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def fetch_daily_candles(token: str, instrument_key: str, from_date: str, to_date: str) -> pd.DataFrame:
    url = f"{BASE_URL}/v3/historical-candle/{_encode_key(instrument_key)}/days/1/{to_date}/{from_date}"
    resp = requests.get(url, headers=_headers(token), timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Upstox daily candle API error {resp.status_code}: {resp.text}")
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"Upstox API returned failure: {payload}")
    return _candles_to_df(payload.get("data", {}).get("candles", []))


def fetch_intraday_historical(token: str, instrument_key: str, interval_minutes: str,
                               from_date: str, to_date: str) -> pd.DataFrame:
    url = (f"{BASE_URL}/v3/historical-candle/{_encode_key(instrument_key)}"
           f"/minutes/{interval_minutes}/{to_date}/{from_date}")
    resp = requests.get(url, headers=_headers(token), timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Upstox historical candle API error {resp.status_code}: {resp.text}")
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"Upstox API returned failure: {payload}")
    return _candles_to_df(payload.get("data", {}).get("candles", []))


def fetch_intraday_historical_chunked(token: str, instrument_key: str, interval_minutes: str,
                                       from_date: str, to_date: str, chunk_days: int = 25) -> pd.DataFrame:
    """
    Upstox's V3 API enforces a maximum date range PER REQUEST for
    minute-level intervals — requesting too wide a span in one call
    returns a UDAPI1148 "Invalid date range" error, even though the data
    itself may exist further back. This splits the requested range into
    chunk_days-sized windows, fetches each separately, and stitches the
    results together so you still get the full history you asked for.
    """
    from datetime import date as _date, timedelta as _timedelta

    start = _date.fromisoformat(from_date)
    end = _date.fromisoformat(to_date)

    frames = []
    chunk_end = end
    while chunk_end >= start:
        chunk_start = max(start, chunk_end - _timedelta(days=chunk_days - 1))
        try:
            df_chunk = fetch_intraday_historical(
                token, instrument_key, interval_minutes,
                chunk_start.isoformat(), chunk_end.isoformat()
            )
            if not df_chunk.empty:
                frames.append(df_chunk)
        except RuntimeError:
            pass  # skip a failed chunk (e.g. no trading days in that window) rather than aborting the whole fetch
        chunk_end = chunk_start - _timedelta(days=1)

    if not frames:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    return combined


def fetch_today_intraday(token: str, instrument_key: str, interval_minutes: str = "5") -> pd.DataFrame:
    url = f"{BASE_URL}/v3/historical-candle/intraday/{_encode_key(instrument_key)}/minutes/{interval_minutes}"
    resp = requests.get(url, headers=_headers(token), timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Upstox intraday candle API error {resp.status_code}: {resp.text}")
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"Upstox API returned failure: {payload}")
    return _candles_to_df(payload.get("data", {}).get("candles", []))
