"""
streamlit_app.py
-----------------
Ascending Triangle Pattern Screener — a Streamlit web app.

Run locally with:
    streamlit run streamlit_app.py

Deployed on Streamlit Community Cloud, this becomes accessible from any
browser, anywhere — no VS Code or local Python environment needed to USE
it (you still need your own Upstox account and a fresh daily access token
to pull data, same as the desktop project).

This app is a SCREENER, not a live trading bot — it runs once per click,
which is exactly what Streamlit is good at. It does not place orders or
run unattended in the background.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import time
from datetime import date, timedelta

from pattern_logic import (
    find_pivots, build_alternating_zigzag, detect_ascending_triangle,
    check_prior_uptrend, check_breakout,
)
from upstox_client import fetch_daily_candles, fetch_intraday_historical
from instrument_lookup import (
    load_instrument_master, find_instrument_key,
    load_complete_instrument_master, build_fno_and_index_watchlist,
)

st.set_page_config(page_title="Ascending Triangle Screener", layout="wide")
st.title("📐 Ascending Triangle Pattern Screener")
st.caption(
    "Flags stocks matching a flat-resistance + rising-lows breakout structure "
    "(4 resistance touches, each low higher than the last, entry on breakout). "
    "This is a structural pattern filter, not a prediction of what happens next."
)

# ---------------------------------------------------------------------
# Sidebar — credentials and settings
# ---------------------------------------------------------------------
with st.sidebar:
    st.header("Upstox Access")
    access_token = st.text_input(
        "Upstox Access Token", type="password",
        help="Generate a fresh one each trading day via Upstox's OAuth login "
             "(token expires ~3:30 AM IST daily). Never shared or stored by this app."
    )
    st.caption("This token is used only for this session's requests and is not saved anywhere.")

    st.divider()
    st.header("Screener Settings")
    timeframe = st.selectbox("Timeframe", ["daily", "60", "15"], index=0,
                              help="'daily' uses daily candles; '60'/'15' use minute candles.")
    tol_pct = st.slider("Resistance tolerance (%)", 0.1, 3.0, 1.0, 0.1,
                         help="How close repeated resistance touches must be to count as 'flat'.")
    min_pairs = st.select_slider("Required touch pairs", options=[3, 4, 5], value=4,
                                  help="4 matches the exact diagram; 3 is a looser/earlier variant.")
    pivot_left = st.slider("Pivot left bars", 1, 5, 2)
    pivot_right = st.slider("Pivot right bars", 1, 5, 2)
    uptrend_lookback = st.slider("Prior-uptrend lookback (bars)", 3, 20, 10)
    uptrend_green_pct = st.slider("Prior-uptrend green-candle %", 0.3, 1.0, 0.6, 0.05)

# ---------------------------------------------------------------------
# Watchlist input
# ---------------------------------------------------------------------
st.subheader("Watchlist")

default_watchlist = "RELIANCE,NSE_EQ|INE002A01018\nGODREJPROP,NSE_EQ|INE484J01027"
if "watchlist_text" not in st.session_state:
    st.session_state.watchlist_text = default_watchlist


@st.cache_data(ttl=43200, show_spinner=False)  # cache 12h — this file is large, don't refetch every click
def _cached_complete_instrument_master():
    return load_complete_instrument_master()


col1, col2 = st.columns([1, 2])
with col1:
    load_fno_clicked = st.button("📥 Load All F&O Stocks + NIFTY/BANKNIFTY/SENSEX")
with col2:
    st.caption(
        "Pulls the CURRENT F&O-eligible stock list live from Upstox's own instrument file "
        "(not a hardcoded list, since NSE reviews and changes this roughly every 6 months) "
        "plus the three index instrument keys. First load downloads a large file — may take "
        "a little while, then it's cached for 12 hours."
    )

if load_fno_clicked:
    progress_placeholder = st.empty()

    def _progress(done, total, symbol):
        progress_placeholder.progress(done / max(total, 1), text=f"Resolving {symbol} ({done}/{total})")

    try:
        with st.spinner("Downloading Upstox's complete instrument master (large file, first time only)..."):
            df_complete = _cached_complete_instrument_master()
        watchlist_dict, debug_info = build_fno_and_index_watchlist(
            df_complete, progress_callback=_progress, debug=True
        )
        progress_placeholder.empty()
        st.session_state.watchlist_text = "\n".join(f"{sym},{key}" for sym, key in watchlist_dict.items())
        st.success(f"Loaded {len(watchlist_dict)} symbols (F&O stocks + indices) into the watchlist below.")

        with st.expander("🔧 Diagnostics (open this if the count above looks too low)"):
            st.write(f"**Total instrument rows in file:** {debug_info['total_rows']:,}")
            st.write(f"**Rows in NSE_FO segment:** {debug_info['nse_fo_rows']:,}")
            st.write("**instrument_type values found within NSE_FO:**")
            st.json(debug_info["instrument_type_counts_in_NSE_FO"])
            st.write(f"**Rows matched as futures contracts:** {debug_info['fo_futures_rows_matched']:,}")
            st.write(f"**Underlying-symbol extraction method used:** `{debug_info['method_used']}`")
            st.write(f"**Underlying-symbol column used (if any):** `{debug_info['underlying_column_used']}`")
            st.write(f"**F&O symbols found before resolving to equity keys:** {debug_info['symbol_count_found']}")
            st.write(f"**Sample symbols found:** {debug_info['sample_symbols']}")
            st.write(f"**Successfully resolved to a cash-equity instrument_key:** {debug_info['resolved_count']}")
            st.write(f"**Could NOT be resolved:** {debug_info['unresolved_count']}")
            if debug_info["unresolved_sample"]:
                st.write(f"**Sample of unresolved symbols:** {debug_info['unresolved_sample']}")
    except Exception as e:
        st.error(f"Could not load F&O list: {e}")

st.write("One stock per line, as `SYMBOL,INSTRUMENT_KEY`. Use the finder below if you don't have a key yet, "
         "or the button above to auto-load the full F&O universe + indices.")
watchlist_text = st.text_area("Watchlist", height=200, label_visibility="collapsed", key="watchlist_text")

with st.expander("🔍 Find an instrument_key for a symbol"):
    lookup_symbol = st.text_input("Symbol to search (e.g. TCS)")
    if st.button("Search"):
        with st.spinner("Downloading Upstox instrument master (first search only, cached after)..."):
            try:
                df_master = load_instrument_master()
                key, _ = find_instrument_key(df_master, lookup_symbol.upper())
                st.success(f"{lookup_symbol.upper()} → `{key}`")
                st.code(f"{lookup_symbol.upper()},{key}", language=None)
            except Exception as e:
                st.error(str(e))

# ---------------------------------------------------------------------
# Run screener
# ---------------------------------------------------------------------
run = st.button("▶ Run Screener", type="primary", disabled=not access_token)
if not access_token:
    st.info("Enter your Upstox access token in the sidebar to enable the screener.")

_watchlist_line_count = len([l for l in watchlist_text.strip().splitlines() if "," in l])
if _watchlist_line_count > 30:
    est_seconds = _watchlist_line_count * 0.6
    st.warning(f"{_watchlist_line_count} symbols in your watchlist — this scan will take roughly "
               f"{est_seconds/60:.1f} minutes (one API call per stock, paced to respect rate limits). "
               f"Keep this browser tab open while it runs.")

if run:
    watchlist = {}
    for line in watchlist_text.strip().splitlines():
        if "," in line:
            sym, key = line.split(",", 1)
            watchlist[sym.strip()] = key.strip()

    if not watchlist:
        st.warning("No valid watchlist entries found. Use the format SYMBOL,INSTRUMENT_KEY per line.")

    results = []
    progress = st.progress(0.0, text="Starting scan...")

    for i, (symbol, instrument_key) in enumerate(watchlist.items()):
        progress.progress((i) / max(len(watchlist), 1), text=f"Scanning {symbol}... ({i}/{len(watchlist)})")
        time.sleep(0.15)  # gentle pacing to avoid hitting Upstox rate limits on large watchlists
        try:
            to_date = date.today().isoformat()
            if timeframe == "daily":
                from_date = (date.today() - timedelta(days=250)).isoformat()
                df = fetch_daily_candles(access_token, instrument_key, from_date, to_date)
            else:
                from_date = (date.today() - timedelta(days=60)).isoformat()
                df = fetch_intraday_historical(access_token, instrument_key, timeframe, from_date, to_date)
        except Exception as e:
            results.append({"symbol": symbol, "status": f"Error: {e}"})
            continue

        if df.empty or len(df) < (2 * min_pairs + 5):
            results.append({"symbol": symbol, "status": "Not enough candle history"})
            continue

        df = df.reset_index(drop=True)
        pivots = find_pivots(df, left=pivot_left, right=pivot_right)
        zigzag = build_alternating_zigzag(pivots)
        pattern = detect_ascending_triangle(zigzag, tol_pct=tol_pct, min_pairs=min_pairs)

        if pattern is None:
            results.append({"symbol": symbol, "status": "No matching structure"})
            continue

        uptrend_ok = check_prior_uptrend(df, pattern["segment"][0][0],
                                          lookback=uptrend_lookback,
                                          green_pct_threshold=uptrend_green_pct)
        breakout = check_breakout(df, pattern)

        if breakout:
            status = f"🚀 BREAKOUT — entry {breakout['entry_price']:.2f}, target {breakout['target_price']:.2f}"
        else:
            status = f"⏳ Formed, awaiting breakout above {pattern['resistance']:.2f}"

        results.append({
            "symbol": symbol,
            "resistance": round(pattern["resistance"], 2),
            "point1_high": round(pattern["point1_high"], 2),
            "point2_low": round(pattern["point2_low"], 2),
            "prior_uptrend_ok": uptrend_ok,
            "status": status,
            "_df": df, "_pattern": pattern,
        })

    progress.progress(1.0, text="Done.")

    st.subheader("Results")
    display_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    st.dataframe(pd.DataFrame(display_rows), use_container_width=True)

    for r in results:
        if "_df" in r:
            with st.expander(f"📈 Chart: {r['symbol']}"):
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(r["_df"]["close"], color="steelblue", linewidth=1, label="Close")
                ax.axhline(r["_pattern"]["resistance"], color="orange", linestyle="--", label="Resistance")
                for idx, price, typ in r["_pattern"]["segment"]:
                    ax.scatter(idx, price, color="green" if typ == "H" else "red", zorder=5)
                ax.legend()
                ax.set_title(f"{r['symbol']} — pattern points marked")
                st.pyplot(fig)

st.divider()
st.caption(
    "This tool flags structural fit only — it is not a prediction of which trade will win. "
    "Always confirm on your own chart, and this is not financial advice."
)
