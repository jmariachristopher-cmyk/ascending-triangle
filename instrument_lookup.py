"""
instrument_lookup.py
----------------------
Downloads Upstox's NSE instrument master and looks up an instrument_key by
trading symbol — used by the app's "Find an instrument_key" helper so
users don't have to run a separate script to get one.

Also pulls the F&O-eligible stock universe LIVE from Upstox's own
"complete" instrument file, rather than a hardcoded list — NSE reviews
and changes the F&O stock list roughly every 6 months, so hardcoding it
here would go stale. Filtering complete.json.gz for segment=NSE_FO,
instrument_type=FUT gives the current list directly from source.
"""

import gzip
import json
import requests
import pandas as pd

INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
COMPLETE_INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Confirmed stable instrument keys for the major indices (these are index
# symbols, not equities, so they aren't in the NSE_EQ lookup below).
INDEX_INSTRUMENT_KEYS = {
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "NIFTY BANK": "NSE_INDEX|Nifty Bank",
    "SENSEX": "BSE_INDEX|SENSEX",
}


def load_instrument_master() -> pd.DataFrame:
    resp = requests.get(INSTRUMENTS_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    raw = gzip.decompress(resp.content)
    data = json.loads(raw)
    return pd.DataFrame(data)


def load_complete_instrument_master() -> pd.DataFrame:
    """
    Downloads Upstox's full multi-segment instrument file (NSE_EQ, NSE_FO,
    BSE_EQ, indices, etc. all in one). This file is large — expect this to
    take a while and use noticeable memory; cache the result (see the
    Streamlit app's @st.cache_data wrapper) rather than calling this often.
    """
    resp = requests.get(COMPLETE_INSTRUMENTS_URL, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    raw = gzip.decompress(resp.content)
    data = json.loads(raw)
    return pd.DataFrame(data)


def get_fno_underlying_symbols(df_complete: pd.DataFrame, debug: bool = False):
    """
    Filters the complete instrument master for NSE F&O futures contracts
    and returns the unique list of underlying stock symbols currently
    eligible for F&O trading — pulled live from Upstox, so it stays
    accurate as NSE adds/removes stocks from the segment over time.

    Robust to Upstox's instrument_type naming (some files use a plain
    "FUT", others use "FUTSTK"/"FUTIDX" — this matches ANY type containing
    "FUT" rather than requiring an exact string, since guessing the exact
    literal wrongly silently returns almost nothing).

    If debug=True, returns (symbols, debug_info) where debug_info is a dict
    with diagnostic details for troubleshooting instead of just the list.
    """
    df_complete.columns = [c.strip() for c in df_complete.columns]

    seg_col = next((c for c in df_complete.columns if c.lower() == "segment"), None)
    type_col = next((c for c in df_complete.columns if c.lower() == "instrument_type"), None)
    if seg_col is None or type_col is None:
        raise RuntimeError(f"Could not find segment/instrument_type columns. Columns: {list(df_complete.columns)}")

    nse_fo = df_complete[df_complete[seg_col].astype(str).str.upper() == "NSE_FO"]
    instrument_type_counts = nse_fo[type_col].value_counts().to_dict()

    fo_futures = nse_fo[nse_fo[type_col].astype(str).str.upper().str.contains("FUT", na=False)]

    underlying_col = next(
        (c for c in df_complete.columns if c.lower() in
         ("underlying_symbol", "asset_symbol", "underlying_key", "name")),
        None
    )

    symbols = []
    method_used = None

    if underlying_col is not None:
        candidate_symbols = sorted(
            fo_futures[underlying_col].dropna().astype(str).str.upper().unique().tolist()
        )
        # Sanity check: NSE currently has on the order of 150-250 F&O stocks.
        # If this column gave us a wildly implausible count (e.g. near-zero,
        # or thousands because it's actually a per-contract description
        # field), don't trust it — fall back to parsing trading_symbol.
        if 20 <= len(candidate_symbols) <= 400:
            symbols = candidate_symbols
            method_used = f"column '{underlying_col}'"

    if not symbols:
        # Fallback: derive the underlying from the leading alphabetic
        # characters of trading_symbol (e.g. "RELIANCE25SEPFUT" -> "RELIANCE").
        sym_col = next((c for c in df_complete.columns if c.lower() in ("trading_symbol", "tradingsymbol")), None)
        if sym_col is not None:
            extracted = fo_futures[sym_col].astype(str).str.upper().str.extract(r"^([A-Z&\-]+)")[0]
            symbols = sorted(extracted.dropna().unique().tolist())
            method_used = f"regex fallback on '{sym_col}'"

    index_like = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT", "SENSEX", "BANKEX"}
    symbols = [s for s in symbols if not any(idx in s for idx in index_like)]

    if debug:
        debug_info = {
            "total_rows": len(df_complete),
            "nse_fo_rows": len(nse_fo),
            "instrument_type_counts_in_NSE_FO": instrument_type_counts,
            "fo_futures_rows_matched": len(fo_futures),
            "underlying_column_used": underlying_col,
            "method_used": method_used,
            "symbol_count_found": len(symbols),
            "sample_symbols": symbols[:15],
        }
        return symbols, debug_info

    return symbols


def find_instrument_key(df: pd.DataFrame, symbol: str):
    df.columns = [c.strip() for c in df.columns]

    sym_cols = [c for c in df.columns if c.lower() in ("trading_symbol", "tradingsymbol")]
    key_cols = [c for c in df.columns if c.lower() in ("instrument_key",)]
    seg_cols = [c for c in df.columns if c.lower() in ("segment",)]
    type_cols = [c for c in df.columns if c.lower() in ("instrument_type",)]

    if not sym_cols or not key_cols:
        raise RuntimeError(f"Could not detect expected columns. Columns found: {list(df.columns)}")

    sym_col, key_col = sym_cols[0], key_cols[0]
    matches = df[df[sym_col].astype(str).str.upper() == symbol.upper()]

    if seg_cols:
        narrowed = matches[matches[seg_cols[0]].astype(str).str.upper() == "NSE_EQ"]
        if len(narrowed) > 0:
            matches = narrowed
    if type_cols:
        narrowed = matches[matches[type_cols[0]].astype(str).str.upper() == "EQ"]
        if len(narrowed) > 0:
            matches = narrowed

    if matches.empty:
        raise ValueError(f"No exact NSE cash-equity match found for '{symbol}'.")

    row = matches.iloc[0]
    return str(row[key_col]), row.to_dict()


def build_fno_and_index_watchlist(df_complete: pd.DataFrame, progress_callback=None, debug: bool = False):
    """
    Returns a dict {symbol: instrument_key} covering every current F&O
    stock's CASH EQUITY instrument_key, plus NIFTY 50 / BANK NIFTY / SENSEX.
    progress_callback(done, total, symbol) is called after each resolution
    if provided, so a UI can show progress.

    If debug=True, returns (watchlist, debug_info) instead of just watchlist.
    """
    if debug:
        fno_symbols, debug_info = get_fno_underlying_symbols(df_complete, debug=True)
    else:
        fno_symbols = get_fno_underlying_symbols(df_complete)
        debug_info = None

    watchlist = dict(INDEX_INSTRUMENT_KEYS)
    unresolved = []

    total = len(fno_symbols)
    for i, symbol in enumerate(fno_symbols):
        try:
            key, _ = find_instrument_key(df_complete, symbol)
            watchlist[symbol] = key
        except Exception:
            unresolved.append(symbol)
        if progress_callback:
            progress_callback(i + 1, total, symbol)

    if debug:
        debug_info["resolved_count"] = len(watchlist) - len(INDEX_INSTRUMENT_KEYS)
        debug_info["unresolved_count"] = len(unresolved)
        debug_info["unresolved_sample"] = unresolved[:15]
        return watchlist, debug_info

    return watchlist
