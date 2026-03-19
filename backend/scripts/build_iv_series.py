#!/usr/bin/env python3
"""
build_iv_series.py  —  OptionsDX CSV → GLD Daily IV Series
============================================================
Parses raw OptionsDX end-of-day options data for GLD and extracts
a clean daily ATM implied volatility (IV) time series.

Output: data/gld_iv_daily.csv
  columns: date, atm_iv, put_iv, call_iv, iv_rank_252, skew (put_iv / call_iv)

Usage:
  # Download free GLD data from optionsdx.com, unzip into data/optionsdx/
  # Then run:
  python scripts/build_iv_series.py

  # Or point at a specific directory:
  python scripts/build_iv_series.py --input-dir /path/to/optionsdx/csv

  # Preview without writing output:
  python scripts/build_iv_series.py --dry-run

OptionsDX Data Format (free tier, end-of-day):
  URL: https://optionsdx.com/product/gld-spdr-gold-shares/
  - Annual CSV files: e.g. GLD_2020.csv, GLD_2021.csv, ...
  - Each row = one option contract at one date
  - ~20-50k rows per year

Key columns used (auto-detected):
  quote_date        — bar date (YYYY-MM-DD)
  expiration_date   — option expiry
  strike            — strike price
  option_type       — 'C' or 'P' (or 'call'/'put')
  implied_volatility — IV as decimal (0.15 = 15%)
  underlying_last / active_underlying_price — spot price
  dte               — days to expiration
  bid_eod / ask_eod — end-of-day bid/ask (used to filter illiquid strikes)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_INPUT_DIR = Path(__file__).parent.parent / "data" / "optionsdx"
DEFAULT_OUTPUT    = Path(__file__).parent.parent / "data" / "gld_iv_daily.csv"

# ATM selection: use options within ±ATM_BAND% of spot price
ATM_BAND_PCT = 0.03   # ±3% of spot = ATM zone

# DTE range for ATM IV extraction: 20–45 DTE options
# (matches our backtest target of 30 DTE; avoids expiry distortion)
DTE_MIN = 15
DTE_MAX = 50

# Minimum bid to filter illiquid/stale quotes
MIN_BID = 0.05


# ─── Column name aliases (OptionsDX has changed formats over the years) ───────

COL_ALIASES = {
    "quote_date":            ["quote_date", "quotedate", "date", "DataDate"],
    "expiration_date":       ["expiration_date", "expiration", "ExpirationDate", "Expiry"],
    "strike":                ["strike", "Strike", "StrikePrice"],
    "option_type":           ["option_type", "type", "OptionType", "CallPut"],
    "implied_volatility":    ["implied_volatility", "iv", "ImpliedVolatility", "IV"],
    "underlying_last":       ["underlying_last", "active_underlying_price",
                              "UnderlyingPrice", "Underlying_Price", "underlying_price"],
    "dte":                   ["dte", "DTE", "days_to_expiry"],
    "bid_eod":               ["bid_eod", "bid", "Bid", "bid_1545"],
    "ask_eod":               ["ask_eod", "ask", "Ask", "ask_1545"],
}


def _resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map canonical names to actual column names found in df."""
    cols_lower = {c.lower(): c for c in df.columns}
    resolved = {}
    for canonical, aliases in COL_ALIASES.items():
        for alias in aliases:
            if alias in df.columns:
                resolved[canonical] = alias
                break
            if alias.lower() in cols_lower:
                resolved[canonical] = cols_lower[alias.lower()]
                break
    return resolved


def load_optionsdx_files(input_dir: Path) -> pd.DataFrame:
    """Load all CSV files from input_dir into a single DataFrame."""
    csv_files = sorted(input_dir.glob("*.csv"))
    if not csv_files:
        # Try one level deeper
        csv_files = sorted(input_dir.glob("**/*.csv"))
    if not csv_files:
        print(f"ERROR: No CSV files found in {input_dir}")
        print("  Download GLD data from optionsdx.com and place CSVs in that directory.")
        sys.exit(1)

    print(f"Found {len(csv_files)} CSV files in {input_dir}")
    chunks = []
    for f in csv_files:
        try:
            chunk = pd.read_csv(f, low_memory=False)
            chunks.append(chunk)
            print(f"  Loaded {f.name}: {len(chunk):,} rows")
        except Exception as e:
            print(f"  WARNING: Could not read {f.name}: {e}")

    if not chunks:
        print("ERROR: No data loaded.")
        sys.exit(1)

    combined = pd.concat(chunks, ignore_index=True)
    print(f"Total rows loaded: {len(combined):,}")
    return combined


def extract_daily_iv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract daily ATM implied volatility from raw options chain data.

    Strategy:
    1. Filter to DTE_MIN–DTE_MAX window (20–45 DTE options)
    2. Find the nearest expiry with sufficient liquidity per day
    3. Select ATM strikes (within ±3% of spot)
    4. Compute ATM IV as average of ATM call IV and ATM put IV
    5. Also record put/call skew
    """
    cols = _resolve_columns(df)

    missing = [k for k in ["quote_date", "expiration_date", "strike", "option_type",
                            "implied_volatility", "underlying_last"]
               if k not in cols]
    if missing:
        print(f"ERROR: Cannot find columns for: {missing}")
        print(f"  Available columns: {list(df.columns[:20])} ...")
        print("  Check COL_ALIASES in this script and add your file's column names.")
        sys.exit(1)

    # Rename to canonical
    rename = {v: k for k, v in cols.items()}
    df = df.rename(columns=rename)

    # Parse dates
    df["quote_date"] = pd.to_datetime(df["quote_date"], errors="coerce")
    df["expiration_date"] = pd.to_datetime(df["expiration_date"], errors="coerce")
    df = df.dropna(subset=["quote_date", "expiration_date", "implied_volatility"])

    # Compute DTE if not present
    if "dte" not in df.columns:
        df["dte"] = (df["expiration_date"] - df["quote_date"]).dt.days

    # Numeric conversions
    df["dte"] = pd.to_numeric(df["dte"], errors="coerce")
    df["implied_volatility"] = pd.to_numeric(df["implied_volatility"], errors="coerce")
    df["underlying_last"] = pd.to_numeric(df["underlying_last"], errors="coerce")
    df["strike"] = pd.to_numeric(df["strike"], errors="coerce")

    # Standardize option type to 'C' / 'P'
    ot = df["option_type"].astype(str).str.strip().str.upper()
    df["option_type"] = ot.map(lambda x: "C" if x in ("C", "CALL") else ("P" if x in ("P", "PUT") else x))
    df = df[df["option_type"].isin(["C", "P"])]

    # Filter bid if available
    if "bid_eod" in df.columns:
        df["bid_eod"] = pd.to_numeric(df["bid_eod"], errors="coerce").fillna(0)
        df = df[df["bid_eod"] >= MIN_BID]

    # Filter sane IV values
    df = df[(df["implied_volatility"] > 0.01) & (df["implied_volatility"] < 3.0)]

    # DTE window filter
    df = df[(df["dte"] >= DTE_MIN) & (df["dte"] <= DTE_MAX)]
    df = df.dropna(subset=["underlying_last", "strike", "dte"])

    print(f"Rows after filters: {len(df):,}")

    results = []
    for quote_dt, grp in df.groupby("quote_date"):
        spot = grp["underlying_last"].median()
        if pd.isna(spot) or spot <= 0:
            continue

        # ATM zone: strikes within ±ATM_BAND_PCT of spot
        atm_lo = spot * (1 - ATM_BAND_PCT)
        atm_hi = spot * (1 + ATM_BAND_PCT)
        atm = grp[(grp["strike"] >= atm_lo) & (grp["strike"] <= atm_hi)]

        if len(atm) < 2:
            # Widen band if too few options
            atm_lo = spot * 0.95
            atm_hi = spot * 1.05
            atm = grp[(grp["strike"] >= atm_lo) & (grp["strike"] <= atm_hi)]

        if atm.empty:
            continue

        calls = atm[atm["option_type"] == "C"]["implied_volatility"]
        puts  = atm[atm["option_type"] == "P"]["implied_volatility"]

        call_iv = calls.median() if not calls.empty else np.nan
        put_iv  = puts.median()  if not puts.empty else np.nan

        # ATM IV = average of ATM call and ATM put (VIX methodology)
        if pd.notna(call_iv) and pd.notna(put_iv):
            atm_iv = (call_iv + put_iv) / 2
        elif pd.notna(call_iv):
            atm_iv = call_iv
        elif pd.notna(put_iv):
            atm_iv = put_iv
        else:
            continue

        skew = (put_iv / call_iv) if (pd.notna(put_iv) and pd.notna(call_iv) and call_iv > 0) else np.nan

        results.append({
            "date":      quote_dt.date(),
            "spot":      round(spot, 2),
            "atm_iv":    round(atm_iv, 4),
            "call_iv":   round(call_iv, 4) if pd.notna(call_iv) else np.nan,
            "put_iv":    round(put_iv, 4)  if pd.notna(put_iv)  else np.nan,
            "skew":      round(skew, 3)    if pd.notna(skew)    else np.nan,
            "n_options": len(atm),
        })

    iv_df = pd.DataFrame(results).sort_values("date").reset_index(drop=True)
    iv_df["date"] = pd.to_datetime(iv_df["date"])
    return iv_df


def compute_iv_rank(iv_series: pd.Series, window: int = 252) -> pd.Series:
    """Rolling 252-day IV rank (0–100)."""
    def _rank(x):
        if len(x) < 10:
            return np.nan
        cur = x.iloc[-1]
        lo  = x.min()
        hi  = x.max()
        if hi == lo:
            return 50.0
        return (cur - lo) / (hi - lo) * 100

    return iv_series.rolling(window, min_periods=20).apply(_rank, raw=False)


def print_summary(iv_df: pd.DataFrame) -> None:
    """Print a human-readable summary of the extracted IV data."""
    print(f"\n{'='*60}")
    print(f"  GLD Daily IV Series — {len(iv_df)} trading days")
    print(f"  Period: {iv_df['date'].min().date()} → {iv_df['date'].max().date()}")
    print(f"{'='*60}")
    print(f"  ATM IV:   min={iv_df['atm_iv'].min():.1%}  "
          f"mean={iv_df['atm_iv'].mean():.1%}  "
          f"max={iv_df['atm_iv'].max():.1%}")
    print(f"  Put/Call Skew (avg): {iv_df['skew'].mean():.3f}  "
          f"(>1.0 means puts pricier than calls — expected)")
    if "iv_rank_252" in iv_df.columns:
        print(f"  IV Rank (252d): mean={iv_df['iv_rank_252'].mean():.1f}  "
              f"days≥40: {(iv_df['iv_rank_252']>=40).sum()} "
              f"({(iv_df['iv_rank_252']>=40).mean():.0%} of days)")
    print(f"\n  Coverage check:")
    # Coverage by year
    iv_df["year"] = iv_df["date"].dt.year
    for yr, grp in iv_df.groupby("year"):
        print(f"    {yr}: {len(grp):3d} days  ATM IV avg={grp['atm_iv'].mean():.1%}")

    # Compare to HV proxy estimate
    print(f"\n  Data quality note:")
    print(f"  If you have yfinance GLD data to compare, run with --compare")
    print(f"  to see real IV vs HV×1.15 proxy divergence.")


def main():
    parser = argparse.ArgumentParser(
        description="Build GLD daily IV series from OptionsDX raw data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SETUP INSTRUCTIONS:
  1. Go to https://optionsdx.com/product/gld-spdr-gold-shares/
  2. Download free end-of-day CSV files (annual, e.g. GLD_2020.csv ... GLD_2025.csv)
  3. Place all CSV files in:  backend/data/optionsdx/
  4. Run:  python scripts/build_iv_series.py

OUTPUT:
  backend/data/gld_iv_daily.csv  — used by backtest.py --iv-data

THEN RUN BACKTEST WITH REAL IV:
  python scripts/backtest.py --years 5 --freq 3 --iv-data data/gld_iv_daily.csv
        """,
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR,
                        help=f"Directory with OptionsDX CSV files (default: {DEFAULT_INPUT_DIR})")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Output CSV path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and print stats without writing output file")
    parser.add_argument("--compare", action="store_true",
                        help="After building IV series, compare real IV vs HV×1.15 proxy")
    args = parser.parse_args()

    if not args.input_dir.exists():
        print(f"\nERROR: Input directory not found: {args.input_dir}")
        print(f"\nSetup instructions:")
        print(f"  1. Go to https://optionsdx.com/product/gld-spdr-gold-shares/")
        print(f"  2. Download free annual CSV files (GLD_20XX.csv)")
        print(f"  3. Place them in: {args.input_dir}")
        print(f"  4. Re-run this script")
        sys.exit(1)

    print(f"Loading OptionsDX data from {args.input_dir} ...")
    raw_df = load_optionsdx_files(args.input_dir)

    print(f"\nExtracting daily ATM IV ...")
    iv_df = extract_daily_iv(raw_df)

    # Add IV rank (rolling 252-day)
    iv_df["iv_rank_252"] = compute_iv_rank(iv_df["atm_iv"]).round(1)

    print_summary(iv_df)

    if args.compare:
        _compare_with_hv_proxy(iv_df)

    if not args.dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        iv_df.to_csv(args.output, index=False)
        print(f"\nSaved → {args.output}")
        print(f"Use in backtest:")
        print(f"  python scripts/backtest.py --years 5 --freq 3 --iv-data {args.output}")
    else:
        print("\n[dry-run] Output not written.")


def _compare_with_hv_proxy(iv_df: pd.DataFrame) -> None:
    """Download GLD from yfinance and compare real IV vs HV×1.15 proxy."""
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed; skipping comparison.")
        return

    print("\nDownloading GLD for HV comparison ...")
    years = max(1, (iv_df["date"].max() - iv_df["date"].min()).days // 365)
    raw = yf.download("GLD", period=f"{years + 1}y", interval="1d",
                      progress=False, auto_adjust=True)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    close = raw["Close"]
    log_ret = np.log(close / close.shift(1))
    hv20 = log_ret.rolling(20).std() * np.sqrt(252)
    hv_proxy = (hv20 * 1.15).rename("hv_proxy")

    merged = iv_df.set_index("date").join(hv_proxy.rename_axis("date"), how="inner")
    merged["iv_vs_proxy"] = merged["atm_iv"] - merged["hv_proxy"]

    print(f"\n  Real IV vs HV×1.15 proxy divergence:")
    print(f"  Mean difference:   {merged['iv_vs_proxy'].mean():+.3f} "
          f"({'real IV higher' if merged['iv_vs_proxy'].mean() > 0 else 'proxy higher'})")
    print(f"  Std of difference: {merged['iv_vs_proxy'].std():.3f}")
    print(f"  Max over-estimate: proxy too high by {(-merged['iv_vs_proxy']).clip(0).max():.3f}")
    print(f"  Max under-estimate: proxy too low by {merged['iv_vs_proxy'].clip(0).max():.3f}")

    # By year breakdown
    merged["year"] = pd.to_datetime(merged.index).year
    print(f"\n  By year:")
    print(f"  {'Year':>5}  {'Real IV':>8}  {'Proxy':>8}  {'Diff':>8}  {'Proxy Error'}")
    for yr, g in merged.groupby("year"):
        ri = g["atm_iv"].mean()
        pr = g["hv_proxy"].mean()
        diff = ri - pr
        err_pct = diff / ri * 100
        print(f"  {yr:>5}  {ri:>7.1%}   {pr:>7.1%}  {diff:>+7.3f}   {err_pct:>+.0f}%")


if __name__ == "__main__":
    main()
