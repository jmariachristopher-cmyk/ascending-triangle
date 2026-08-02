"""
debug_instrument_schema.py
---------------------------
One-off diagnostic script — run this once to find out exactly how Upstox's
complete instrument file is structured, so instrument_lookup.py's F&O
filtering logic can be corrected to match it precisely (rather than guessing).

Usage:
    python debug_instrument_schema.py

Output:
  - Prints all column names in the file
  - Prints value counts of instrument_type under the NSE_FO segment
    (reveals whether Upstox uses "FUT" vs "FUTSTK"/"FUTIDX" etc.)
  - Saves a small sample of NSE_FO rows to fo_sample.csv so you can open
    it and see exactly which column holds the underlying stock symbol
"""

from instrument_lookup import load_complete_instrument_master

print("Downloading Upstox's complete instrument master (large file, please wait)...")
df = load_complete_instrument_master()

print("\n=== ALL COLUMNS ===")
print(df.columns.tolist())

seg_col = next((c for c in df.columns if c.lower() == "segment"), None)
type_col = next((c for c in df.columns if c.lower() == "instrument_type"), None)

if seg_col is None or type_col is None:
    print("\nCould not find 'segment' or 'instrument_type' columns directly — "
          "check the column list above for the closest equivalents.")
else:
    fo = df[df[seg_col].astype(str).str.upper() == "NSE_FO"]
    print(f"\n=== Rows where {seg_col} == NSE_FO: {len(fo)} ===")
    print(f"\n=== Value counts of '{type_col}' within NSE_FO ===")
    print(fo[type_col].value_counts())

    sample = fo.head(15)
    sample.to_csv("fo_sample.csv", index=False)
    print(f"\nSaved a 15-row sample of NSE_FO instruments to fo_sample.csv")
    print("Open that file (Excel, or 'code fo_sample.csv' in VS Code) and look for "
          "whichever column holds the plain underlying stock symbol, e.g. 'RELIANCE', 'TCS'.")

print("\nDone. Paste the printed output above (columns list + value_counts) back into the chat.")
