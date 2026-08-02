"""
Core detection logic for the ascending-triangle pattern:
  point1(H) - point2(L) - point3(H~=1) - point4(L>point2) - point5(H~=1)
  - point6(L>point4) - point7(H~=1) - point8(L>point6) - breakout above resistance

Standalone module so the logic can be unit-tested with synthetic data before
wiring to live Upstox candles.
"""
import pandas as pd
import numpy as np


def find_pivots(df: pd.DataFrame, left: int = 2, right: int = 2):
    """Fractal-style swing high/low detection."""
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    pivots = []
    for i in range(left, n - right):
        window_high = highs[i - left:i + right + 1]
        if highs[i] == window_high.max():
            pivots.append((i, highs[i], "H"))
        window_low = lows[i - left:i + right + 1]
        if lows[i] == window_low.min():
            pivots.append((i, lows[i], "L"))
    return pivots


def build_alternating_zigzag(pivots):
    """Collapse raw pivots into a strictly alternating H/L sequence, keeping
    the more extreme point whenever two same-type pivots occur back to back."""
    pivots_sorted = sorted(pivots, key=lambda p: p[0])
    zigzag = []
    for idx, price, typ in pivots_sorted:
        if not zigzag:
            zigzag.append([idx, price, typ])
            continue
        last_idx, last_price, last_type = zigzag[-1]
        if typ == last_type:
            if typ == "H" and price > last_price:
                zigzag[-1] = [idx, price, typ]
            elif typ == "L" and price < last_price:
                zigzag[-1] = [idx, price, typ]
        else:
            zigzag.append([idx, price, typ])
    return zigzag


def detect_ascending_triangle(zigzag, tol_pct: float = 0.6, min_pairs: int = 4):
    """
    Looks for min_pairs alternating (H, L) pairs at the END of the zigzag,
    where all highs are within tol_pct% of each other (flat resistance) and
    lows are strictly increasing (rising higher lows). Must end on a Low
    (the most recent confirmed support, awaiting breakout).
    """
    needed = 2 * min_pairs
    if len(zigzag) < needed:
        return None

    segment = zigzag[-needed:]
    types = [p[2] for p in segment]
    expected = ["H", "L"] * min_pairs
    if types != expected:
        return None

    highs = [p[1] for p in segment if p[2] == "H"]
    lows = [p[1] for p in segment if p[2] == "L"]

    href = highs[0]
    if not all(abs(h - href) / href * 100 <= tol_pct for h in highs):
        return None

    if not all(lows[i] < lows[i + 1] for i in range(len(lows) - 1)):
        return None

    return {
        "segment": segment,
        "highs": highs,
        "lows": lows,
        "resistance": sum(highs) / len(highs),
        "point1_high": highs[0],
        "point2_low": lows[0],
        "last_support_idx": segment[-1][0],
    }


def check_prior_uptrend(df, point1_idx, lookback=10, green_pct_threshold=0.6):
    """Rule 1: point 1 should be preceded by a clear preceding up-move."""
    start = max(0, point1_idx - lookback)
    if start >= point1_idx:
        return None  # not enough data to judge
    window = df.iloc[start:point1_idx]
    green_pct = (window["close"] > window["open"]).mean()
    return green_pct >= green_pct_threshold


def check_breakout(df, pattern, buffer_pct: float = 0.05):
    """
    Scans candles AFTER the last confirmed support (point 8) for a close
    above the resistance level (rule 9: 'breakout candle ... is entry').
    Returns entry info if found, else None (still waiting).
    """
    resistance = pattern["resistance"]
    trigger_level = resistance * (1 + buffer_pct / 100)
    after = df.iloc[pattern["last_support_idx"] + 1:]

    for idx, row in after.iterrows():
        if row["close"] > trigger_level:
            entry_price = row["close"]
            target = entry_price + (pattern["point1_high"] - pattern["point2_low"])
            return {
                "breakout_index": idx,
                "entry_price": entry_price,
                "target_price": target,
                "resistance": resistance,
            }
    return None
