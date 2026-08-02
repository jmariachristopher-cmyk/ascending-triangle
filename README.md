# Ascending Triangle Pattern Screener (Streamlit)

A standalone web app version of the pattern screener — scans a watchlist
for the flat-resistance + rising-lows breakout structure, right from your
browser, from anywhere, once deployed.

This is a **screener you click to run**, not an unattended live trading
bot — that's exactly what Streamlit is good at, unlike the always-on
`live_bot.py` in the main desktop project.

## Files
```
streamlit_app.py       # the app itself
pattern_logic.py        # pattern detection math (pivots, zigzag, triangle match)
upstox_client.py         # Upstox REST calls (candles), token passed in per-session
instrument_lookup.py     # in-app symbol -> instrument_key finder
requirements.txt
.gitignore
```

## Run it locally first (recommended before deploying)

1. Open this folder in VS Code
2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Run:
   ```powershell
   streamlit run streamlit_app.py
   ```
   This opens the app in your browser at `http://localhost:8501`.
5. Paste in your Upstox access token (generate one the same way as the
   desktop project — via Upstox's OAuth login, it expires daily), add
   your watchlist, and click **Run Screener**.

## Step-by-step: publish to GitHub

1. In VS Code, open the **Source Control** panel (`Ctrl+Shift+G`)
2. Click **Initialize Repository** if prompted
3. Stage all files, type a commit message (e.g. `Initial commit`), click
   **✓ Commit**
4. Click **Publish to GitHub** → choose **Public** or **Private**
   (Public is fine here — there are no secrets in this repo; the Upstox
   token is entered by the user in the browser each session, never stored
   in code)

(If you get a "configure user.name/user.email" error, run in the terminal:
```powershell
git config --global user.email "you@example.com"
git config --global user.name "yourname"
```
then commit again.)

## Step-by-step: deploy to Streamlit Community Cloud (free)

1. Go to https://share.streamlit.io and sign in with your GitHub account
2. Click **"New app"**
3. Choose:
   - **Repository**: the one you just published (e.g. `yourname/pattern_screener_app`)
   - **Branch**: `main`
   - **Main file path**: `streamlit_app.py`
4. Click **Deploy**

Streamlit Cloud will install `requirements.txt` automatically and give you
a public URL like `https://yourname-pattern-screener-app.streamlit.app` —
open that from any phone, laptop, or browser, anywhere, and the screener
runs live using whatever Upstox token you paste in that session.

## Important notes

- **No secrets are stored in the repo or on Streamlit Cloud** — you paste
  your Upstox access token into the app's sidebar each time you use it,
  and it only lives in that browser session's memory. Since Upstox tokens
  expire daily anyway, there's nothing meaningful to persist.
- **This app does not place orders.** It only reads candle data and shows
  you pattern matches — there is no order-placement code in this project
  at all, by design, since an always-on public web app is the wrong place
  for unattended live trading.
- Free Streamlit Cloud apps **sleep after a period of inactivity** and
  wake up on the next visit (may take a few seconds) — normal behavior,
  not a bug.
- This tool flags structural pattern fit only — it is not a prediction of
  outcome and not financial advice. Always confirm on your own chart.
