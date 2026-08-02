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


def fetch_today_intraday(token: str, instrument_key: str, interval_minutes: str = "5") -> pd.DataFrame:
    url = f"{BASE_URL}/v3/historical-candle/intraday/{_encode_key(instrument_key)}/minutes/{interval_minutes}"
    resp = requests.get(url, headers=_headers(token), timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Upstox intraday candle API error {resp.status_code}: {resp.text}")
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"Upstox API returned failure: {payload}")
    return _candles_to_df(payload.get("data", {}).get("candles", []))
