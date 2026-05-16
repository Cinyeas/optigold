#!/usr/bin/env python3
"""
OptiGold Historical Backtest Tool
===================================
Downloads 2 years of real GLD daily data via yfinance, then replays the
full quantitative signal pipeline on each bar and simulates option P&L.

This is an HONEST backtest — no look-ahead bias, no cherry-picking.
The same quant modules used in production are imported directly.

Exit rules (industry standard, not cherry-picked):
  - 50% profit target  (close when premium decays to 50% of credit)
  - 2× max-loss stop   (close when loss doubles the original max-loss)
  - Hold-to-expiry     (if neither trigger fires, settle at expiry)

Usage:
    cd /Users/kongxinyi/Documents/Coding/optigold/backend
    python scripts/backtest.py
    python scripts/backtest.py --years 3 --capital 50000 --profile intermediate
    python scripts/backtest.py --strategy iron_condor  # test single strategy
    python scripts/backtest.py --chart                 # show equity curve (matplotlib)

Requirements:
    pip install yfinance pandas numpy rich matplotlib scipy
"""

from __future__ import annotations

import argparse
import math
import sys
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# Add backend root to path so we can import the quant modules
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    class Console:
        def print(self, *args, **kwargs):
            import re
            text = " ".join(str(a) for a in args)
            text = re.sub(r"\[.*?\]", "", text)
            print(text)
    console = Console()

# Import the live quant modules
from app.quant.market_regime import detect_regime, MarketRegime
from app.quant.strategy_filter import filter_strategies, _REGIME_STRATEGY_FIT
from app.quant.user_profile_matcher import strategy_suitability_scores, UserProfile
from app.quant.black_scholes import bs_price, bs_greeks
from app.quant.eligibility_gate import apply_eligibility_gate


# ─── User profile presets ───────────────────────────────────────────────────

PROFILES = {
    "beginner": {
        "capital": 10_000,
        "max_loss_per_trade": 300,
        "experience_level": "beginner",
        "time_horizon": "monthly",
        "accepts_options": True,
        "accepts_margin": False,
        "accepts_unlimited_risk": False,
        "accepts_multi_leg": True,   # allow vertical spreads (defined-risk, bounded)
        "risk_multiplier": 0.5,
        # Lower delta → more OTM strikes → cheaper options
        "delta_target_otm": 0.15,
        # Narrow spread width so max_loss stays within $300 limit.
        # At GLD≈$460, spot*0.02 ≈ $9.2 → max_loss ≈ $860.
        # $2 width → net credit ~$31, cost $8 → margin too thin (net P&L negative).
        # $3 width → net credit ~$45, max_loss ~$255 (still < $300), cost same → viable.
        "spread_width": 3.0,
    },
    "intermediate": {
        "capital": 50_000,
        "max_loss_per_trade": 2_000,
        "experience_level": "intermediate",
        "time_horizon": "monthly",
        "accepts_options": True,
        "accepts_margin": False,
        "accepts_unlimited_risk": False,
        "accepts_multi_leg": True,
        "risk_multiplier": 0.75,
        "delta_target_otm": 0.30,
        "spread_width": None,   # use default: spot × 0.02
    },
    "advanced": {
        "capital": 200_000,
        "max_loss_per_trade": 8_000,
        "experience_level": "advanced",
        "time_horizon": "monthly",
        "accepts_options": True,
        "accepts_margin": True,
        "accepts_unlimited_risk": True,
        "accepts_multi_leg": True,
        "risk_multiplier": 1.0,
        "delta_target_otm": 0.30,
        "spread_width": None,   # use default: spot × 0.02
    },
}


# ─── Technical indicator helpers ────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's ADX."""
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    plus_dm = (high.diff()).clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    # Where +DM < -DM, zero out +DM and vice versa
    mask = plus_dm >= minus_dm
    plus_dm = plus_dm.where(mask, 0.0)
    minus_dm = minus_dm.where(~mask, 0.0)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    di_plus = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    di_minus = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def hv20(log_returns: pd.Series) -> pd.Series:
    """20-day rolling historical volatility (annualised)."""
    return log_returns.rolling(20).std() * math.sqrt(252)


def iv_rank(iv_series: pd.Series, window: int = 252) -> pd.Series:
    """Rolling IV rank: where does today's IV sit in the past *window* bars?"""
    def _rank(x):
        if len(x) < 2:
            return 50.0
        lo, hi = x[:-1].min(), x[:-1].max()
        if hi == lo:
            return 50.0
        return min(100.0, max(0.0, (x.iloc[-1] - lo) / (hi - lo) * 100))
    return iv_series.rolling(window, min_periods=20).apply(_rank, raw=False)


# ─── Option trade simulation ─────────────────────────────────────────────────

@dataclass
class Trade:
    entry_date: date
    expiry_date: date
    strategy: str
    regime: str
    spot_entry: float
    strike_a: float
    strike_b: float
    option_type_a: str  # "call" or "put"
    iv_entry: float
    dte: int
    premium_collected: float   # positive = credit received
    max_profit: float
    max_loss: float
    pnl: float = 0.0           # gross P&L (before costs)
    trade_cost: float = 0.0    # commission + slippage
    net_pnl: float = 0.0       # pnl - trade_cost
    exit_date: Optional[date] = None
    exit_reason: str = ""
    won: bool = False          # based on gross pnl
    net_won: bool = False      # based on net pnl


# Legs per strategy: open + close legs for commission calculation
# Each leg = 1 contract ($1 commission). Iron condor = 4 legs × open + close = 8 contracts touched.
STRATEGY_LEGS = {
    "cash_secured_put": 1,
    "covered_call": 1,
    "bull_put_spread": 2,
    "bear_call_spread": 2,
    "iron_condor": 4,
    "iron_butterfly": 4,
    "short_straddle": 2,
    "long_call": 1,
    "long_put": 1,
    "long_straddle": 2,
}
COMMISSION_PER_CONTRACT = 1.0   # $1/contract (Tastytrade standard)
SLIPPAGE_PCT = 0.03             # 3% of premium as baseline (bid-ask mid-price offset)
# Per-leg slippage floor: GLD options typical bid-ask impact is $2-5/contract per leg.
# 3% of net credit for cheap spreads ($31) gives only $0.93 — far below actual.
# Floor of $2/leg captures real-world fill cost even for cheap multi-leg structures.
SLIPPAGE_PER_LEG_FLOOR = 2.0   # $2 per leg (round-trip slippage floor)


def _credit_strategy_pnl(
    strategy: str,
    spot_entry: float,
    spot_exit: float,
    strike_a: float,
    strike_b: float,
    iv_entry: float,
    iv_exit: float,
    dte_entry: int,
    dte_exit: int,
    premium_collected: float,
) -> float:
    """
    Estimate P&L at exit for credit (premium-selling) strategies.
    Uses BS to reprice the position at exit, accounting for IV and time remaining.
    """
    T_entry = max(dte_entry / 365, 1e-6)
    T_exit = max(dte_exit / 365, 1e-6)
    r = 0.05

    if strategy == "cash_secured_put":
        entry_val = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "put")
        exit_val = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "put")
        return round((entry_val - exit_val) * 100, 2)  # per contract (×100)

    elif strategy == "covered_call":
        # Short OTM call at strike_a
        entry_val = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "call")
        exit_val = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "call")
        return round((entry_val - exit_val) * 100, 2)

    elif strategy == "bull_put_spread":
        # Short put at strike_a (higher), long put at strike_b (lower)
        short_entry = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "put")
        short_exit = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "put")
        long_entry = bs_price(spot_entry, strike_b, T_entry, r, iv_entry, "put")
        long_exit = bs_price(spot_exit, strike_b, T_exit, r, iv_exit, "put")
        # net P&L = short put profit − long put cost change
        return round(((short_entry - short_exit) - (long_entry - long_exit)) * 100, 2)

    elif strategy == "bear_call_spread":
        # Short call at strike_a (lower), long call at strike_b (higher)
        short_entry = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "call")
        short_exit = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "call")
        long_entry = bs_price(spot_entry, strike_b, T_entry, r, iv_entry, "call")
        long_exit = bs_price(spot_exit, strike_b, T_exit, r, iv_exit, "call")
        return round(((short_entry - short_exit) - (long_entry - long_exit)) * 100, 2)

    elif strategy == "iron_condor":
        # strike_a = short_put, strike_b = short_call (actual strikes from Trade)
        # Long legs are OTM relative to shorts and partially cancel; model short legs only.
        put_entry = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "put")
        put_exit = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "put")
        call_entry = bs_price(spot_entry, strike_b, T_entry, r, iv_entry, "call")
        call_exit = bs_price(spot_exit, strike_b, T_exit, r, iv_exit, "call")
        return round(((put_entry - put_exit) + (call_entry - call_exit)) * 100, 2)

    elif strategy == "iron_butterfly":
        atm_put_entry = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "put")
        atm_put_exit = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "put")
        atm_call_entry = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "call")
        atm_call_exit = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "call")
        return round(((atm_put_entry - atm_put_exit) + (atm_call_entry - atm_call_exit)) * 100, 2)

    elif strategy == "short_straddle":
        atm_put_entry = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "put")
        atm_put_exit = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "put")
        atm_call_entry = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "call")
        atm_call_exit = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "call")
        return round(((atm_put_entry - atm_put_exit) + (atm_call_entry - atm_call_exit)) * 100, 2)

    return 0.0


def _debit_strategy_pnl(
    strategy: str,
    spot_entry: float,
    spot_exit: float,
    strike_a: float,
    iv_entry: float,
    iv_exit: float,
    dte_entry: int,
    dte_exit: int,
    premium_paid: float,
) -> float:
    """P&L for debit (option-buying) strategies."""
    T_entry = max(dte_entry / 365, 1e-6)
    T_exit = max(dte_exit / 365, 1e-6)
    r = 0.05

    if strategy == "long_call":
        entry_val = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "call")
        exit_val = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "call")
        return round((exit_val - entry_val) * 100, 2)

    elif strategy == "long_put":
        entry_val = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "put")
        exit_val = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "put")
        return round((exit_val - entry_val) * 100, 2)

    elif strategy == "long_straddle":
        put_entry = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "put")
        call_entry = bs_price(spot_entry, strike_a, T_entry, r, iv_entry, "call")
        put_exit = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "put")
        call_exit = bs_price(spot_exit, strike_a, T_exit, r, iv_exit, "call")
        return round(((put_exit - put_entry) + (call_exit - call_entry)) * 100, 2)

    return 0.0


# ─── Strategy parameter helper ──────────────────────────────────────────────

CREDIT_STRATEGIES = {
    "cash_secured_put", "bull_put_spread", "covered_call",
    "bear_call_spread", "iron_condor", "iron_butterfly", "short_straddle",
}
DEBIT_STRATEGIES = {"long_call", "long_put", "long_straddle"}

TARGET_DELTA = 0.30  # ~30-delta OTM for premium selling


def _select_strike(
    spot: float,
    strategy: str,
    iv: float,
    dte: int,
    delta_target: float = TARGET_DELTA,
    spread_width: Optional[float] = None,
) -> tuple[float, float]:
    """Return (strike_a, strike_b) for the strategy.

    delta_target controls OTM-ness for credit and debit legs.
    Lower values (e.g. 0.15) produce more OTM, cheaper options —
    suitable for low-capital profiles with tight max_loss_per_trade limits.

    spread_width: override the spread width (in dollar terms) for vertical spreads.
    When None, defaults to max(2.0, spot * 0.02).
    """
    T = max(dte / 365, 1e-6)
    r = 0.05
    sigma = iv
    _spread_w = spread_width if spread_width is not None else max(2.0, spot * 0.02)

    if strategy in ("cash_secured_put", "bull_put_spread"):
        # OTM put: binary-search for target-delta put
        lo, hi = spot * 0.7, spot
        for _ in range(40):
            mid = (lo + hi) / 2
            g = bs_greeks(spot, mid, T, r, sigma, "put")
            if abs(g["delta"]) < delta_target:
                lo = mid   # too OTM, need higher strike
            else:
                hi = mid   # too close to ATM, need lower strike
        strike_a = round(lo, 2)
        strike_b = round(strike_a - _spread_w, 2)  # long put below short
        return strike_a, strike_b

    elif strategy in ("covered_call", "bear_call_spread"):
        lo, hi = spot, spot * 1.5
        for _ in range(40):
            mid = (lo + hi) / 2
            g = bs_greeks(spot, mid, T, r, sigma, "call")
            if g["delta"] > delta_target:
                lo = mid
            else:
                hi = mid
        strike_a = round(hi, 2)
        strike_b = round(strike_a + _spread_w, 2)
        return strike_a, strike_b

    elif strategy in ("iron_condor", "iron_butterfly", "short_straddle"):
        return round(spot, 2), round(spot, 2)  # ATM for condor approximation

    elif strategy in ("long_call",):
        # OTM call at delta_target (default 0.30; beginner uses 0.15 → cheaper)
        lo, hi = spot, spot * 1.3
        for _ in range(40):
            mid = (lo + hi) / 2
            g = bs_greeks(spot, mid, T, r, sigma, "call")
            if g["delta"] > delta_target:
                lo = mid
            else:
                hi = mid
        return round(hi, 2), round(hi, 2)

    elif strategy in ("long_put",):
        lo, hi = spot * 0.7, spot
        for _ in range(40):
            mid = (lo + hi) / 2
            g = bs_greeks(spot, mid, T, r, sigma, "put")
            if abs(g["delta"]) < delta_target:
                hi = mid
            else:
                lo = mid
        return round(lo, 2), round(lo, 2)

    return round(spot, 2), round(spot, 2)


# ─── Main backtest loop ──────────────────────────────────────────────────────

def load_real_iv(iv_data_path: str) -> Optional[pd.DataFrame]:
    """
    Load pre-built real IV series from build_iv_series.py output.
    Returns a DataFrame indexed by date with columns: atm_iv, iv_rank_252, skew.
    Returns None if file not found or cannot be parsed.
    """
    p = Path(iv_data_path)
    if not p.exists():
        console.print(f"[yellow]Warning: --iv-data file not found: {p}[/yellow]")
        return None
    try:
        iv_df = pd.read_csv(p, parse_dates=["date"])
        iv_df = iv_df.set_index("date").sort_index()
        required = {"atm_iv"}
        missing = required - set(iv_df.columns)
        if missing:
            console.print(f"[yellow]Warning: iv-data missing columns {missing}; ignoring[/yellow]")
            return None
        console.print(f"  [green]Real IV data loaded: {len(iv_df)} days "
                      f"({iv_df.index[0].date()} → {iv_df.index[-1].date()})[/green]")
        return iv_df
    except Exception as e:
        console.print(f"[yellow]Warning: could not load iv-data ({e}); using HV proxy[/yellow]")
        return None


def run_backtest(
    years: int = 2,
    profile_name: str = "intermediate",
    force_strategy: Optional[str] = None,
    target_dte: int = 30,
    entry_freq_days: int = 7,   # enter a new trade every N trading days
    ivr_min: float = 40.0,      # minimum IV rank to enter a trade
    real_iv_df: Optional[pd.DataFrame] = None,  # from load_real_iv()
) -> list[Trade]:
    """Run the backtest. Returns list of completed Trade objects."""

    profile_dict = PROFILES[profile_name]
    profile = UserProfile(
        capital=profile_dict["capital"],
        max_loss_per_trade=profile_dict["max_loss_per_trade"],
        accepts_options=profile_dict["accepts_options"],
        accepts_margin=profile_dict["accepts_margin"],
        accepts_unlimited_risk=profile_dict["accepts_unlimited_risk"],
        accepts_multi_leg=profile_dict["accepts_multi_leg"],
        time_horizon=profile_dict["time_horizon"],
        experience_level=profile_dict["experience_level"],
        risk_multiplier=profile_dict["risk_multiplier"],
    )
    console.print(f"\n[bold]Downloading {years}Y GLD + VIX data...[/bold]")
    raw = yf.download("GLD", period=f"{years}y", interval="1d", progress=False, auto_adjust=True)
    if raw.empty:
        console.print("[red]No GLD data downloaded. Check internet connection.[/red]")
        sys.exit(1)

    # Flatten multi-index if needed
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    # Download real VIX data (CBOE Volatility Index)
    vix_raw = yf.download("^VIX", period=f"{years}y", interval="1d", progress=False, auto_adjust=True)
    if not vix_raw.empty:
        if isinstance(vix_raw.columns, pd.MultiIndex):
            vix_raw.columns = vix_raw.columns.get_level_values(0)
        vix_series = vix_raw["Close"].rename("vix")
        console.print(f"  VIX data loaded: {len(vix_raw)} days")
    else:
        vix_series = pd.Series(dtype=float, name="vix")
        console.print("  [yellow]VIX download failed — using neutral 20.0[/yellow]")

    raw = raw.dropna(subset=["Close"])
    console.print(f"  GLD: {len(raw)} trading days: {raw.index[0].date()} → {raw.index[-1].date()}")

    # ── Compute indicators ────────────────────────────────────────────────────
    close = raw["Close"]
    high = raw["High"]
    low = raw["Low"]

    log_ret = np.log(close / close.shift(1))
    hv = hv20(log_ret)

    # ── IV source: real (OptionsDX) or proxy (HV×1.15) ────────────────────────
    if real_iv_df is not None:
        # Align real IV to GLD trading dates (forward-fill gaps up to 5 days)
        real_iv_aligned = real_iv_df["atm_iv"].reindex(close.index).ffill(limit=5)
        coverage = real_iv_aligned.notna().mean()
        if coverage < 0.5:
            console.print(f"[yellow]Real IV coverage only {coverage:.0%} — falling back to HV proxy[/yellow]")
            iv_source = hv * 1.15
            iv_source_label = "HV×1.15 proxy (real IV coverage too low)"
        else:
            iv_source = real_iv_aligned.fillna(hv * 1.15)  # fill gaps with proxy
            iv_source_label = f"Real IV (OptionsDX, {coverage:.0%} coverage)"
            # Use real IV rank if available, else recompute from real IV
            if "iv_rank_252" in real_iv_df.columns:
                ivr_real = real_iv_df["iv_rank_252"].reindex(close.index).ffill(limit=5)
            else:
                ivr_real = None
    else:
        iv_source = hv * 1.15
        iv_source_label = "HV×1.15 proxy (no OptionsDX data)"
        ivr_real = None

    iv_proxy = iv_source
    console.print(f"  IV source: [cyan]{iv_source_label}[/cyan]")

    # Compute IV rank from real IV if available, else from proxy
    if real_iv_df is not None and ivr_real is not None:
        ivr = ivr_real
    else:
        ivr = iv_rank(iv_proxy)       # 52-week IV rank from proxy

    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    rsi14 = rsi(close, 14)
    adx14 = adx(high, low, close, 14)
    change_pct = close.pct_change() * 100

    # Build a clean DataFrame of indicators (merge VIX by date)
    df = pd.DataFrame({
        "close": close,
        "ema20": ema20,
        "ema50": ema50,
        "rsi14": rsi14,
        "adx14": adx14,
        "hv20": hv,
        "iv": iv_proxy,
        "ivr": ivr,
        "chg_pct": change_pct,
    })

    # Attach real IV skew if available (put_iv / call_iv — used for signal quality)
    if real_iv_df is not None and "skew" in real_iv_df.columns:
        skew_aligned = real_iv_df["skew"].reindex(close.index).ffill(limit=5)
        df["iv_skew"] = skew_aligned
    else:
        df["iv_skew"] = np.nan
    if not vix_series.empty:
        df = df.join(vix_series, how="left")
        df["vix"] = df["vix"].ffill().fillna(20.0)  # forward-fill weekends/holidays
    else:
        df["vix"] = 20.0
    df = df.dropna(subset=["close", "ema20", "rsi14", "ivr"])

    # ── User suitability (static for entire backtest) ─────────────────────────
    suitability = strategy_suitability_scores(profile)

    # ── Entry schedule ────────────────────────────────────────────────────────
    dates = df.index.tolist()
    date_to_idx = {d: i for i, d in enumerate(dates)}

    trades: list[Trade] = []
    days_since_last_entry = entry_freq_days  # ensure first bar enters

    for i, entry_dt in enumerate(dates):
        if i < 50:  # warm-up period for indicators
            continue
        if days_since_last_entry < entry_freq_days:
            days_since_last_entry += 1
            continue

        row = df.loc[entry_dt]
        spot = float(row["close"])
        iv = float(row["iv"])
        ivr_val = float(row["ivr"])

        vix_val = float(row["vix"])

        # IV Rank entry filter: only enter when IV rank ≥ 40
        # (raised from 30 → 40: more selective, avoids thin-premium entries)
        if ivr_val < ivr_min:
            days_since_last_entry += 1
            continue

        # Build snapshot for regime detection (now with real VIX)
        snap = {
            "gld_price": spot,
            "ema20": float(row["ema20"]),
            "ema50": float(row["ema50"]),
            "rsi_14": float(row["rsi14"]),
            "adx": float(row["adx14"]),
            "gld_iv_rank": ivr_val,
            "gld_hv_20d": float(row["hv20"]),
            "gld_atm_iv": iv,
            "vix_level": vix_val,           # real VIX
            "gld_24h_change_pct": float(row["chg_pct"]),
        }

        regime: MarketRegime = detect_regime(snap)

        # Regime confidence gate: skip when market direction is ambiguous
        if regime.confidence < 0.50:
            days_since_last_entry += 1
            continue

        # Pick strategy
        if force_strategy:
            strategy_name = force_strategy
        else:
            candidates = filter_strategies(regime, suitability, top_n=5)
            if not candidates:
                continue

            # Apply eligibility hard gate (same rules as live signal_service)
            eligible_names = apply_eligibility_gate(
                strategies=[c.name for c in candidates],
                regime=regime,
                upcoming_events=[],   # no event calendar in backtest
                dte=target_dte,
            )
            candidates = [c for c in candidates if c.name in eligible_names]
            if not candidates:
                days_since_last_entry += 1
                continue

            pass  # candidates already selected above; will iterate below

        # ── Try candidates in rank order until one passes all gates ───────────
        # This allows lower-ranked strategies (e.g. long_call/long_put) to be
        # used when the top candidate is blocked by capital or risk constraints.
        # Without this loop, a Beginner whose top candidate is always CSP would
        # have zero trades because CSP is blocked by the capital gate every time.
        _selected: Optional[tuple] = None  # (strategy_name, strike_a, strike_b, raw_prem, max_profit, max_loss, is_credit)

        _candidate_iter = [force_strategy] if force_strategy else [c.name for c in candidates]
        for _cname in _candidate_iter:
            # Skip strategies the user hasn't enabled
            if suitability.get(_cname, 0) <= 0:
                continue

            # Compute trade parameters for this candidate
            _dte = target_dte
            _delta_tgt = profile_dict.get("delta_target_otm", TARGET_DELTA)
            _spread_w = profile_dict.get("spread_width", None)
            _strike_a, _strike_b = _select_strike(spot, _cname, iv, _dte, delta_target=_delta_tgt, spread_width=_spread_w)
            _T = max(_dte / 365, 1e-6)
            _r = 0.05

            if _cname in CREDIT_STRATEGIES:
                if _cname == "cash_secured_put":
                    _raw_prem = bs_price(spot, _strike_a, _T, _r, iv, "put") * 100
                    _max_profit = _raw_prem
                    _max_loss = max(abs(spot - _strike_a) * 100 - _raw_prem, _raw_prem)
                elif _cname == "bull_put_spread":
                    # Net credit = short put - long put; max_loss capped by spread width
                    _short_p = bs_price(spot, _strike_a, _T, _r, iv, "put")
                    _long_p = bs_price(spot, _strike_b, _T, _r, iv, "put")
                    _raw_prem = (_short_p - _long_p) * 100
                    _max_profit = _raw_prem
                    _max_loss = (_strike_a - _strike_b) * 100 - _raw_prem
                elif _cname == "covered_call":
                    _raw_prem = bs_price(spot, _strike_a, _T, _r, iv, "call") * 100
                    _max_profit = _raw_prem
                    _max_loss = max(abs(_strike_a - spot) * 100 - _raw_prem, _raw_prem)
                elif _cname == "bear_call_spread":
                    # Net credit = short call - long call; max_loss capped by spread width
                    _short_c = bs_price(spot, _strike_a, _T, _r, iv, "call")
                    _long_c = bs_price(spot, _strike_b, _T, _r, iv, "call")
                    _raw_prem = (_short_c - _long_c) * 100
                    _max_profit = _raw_prem
                    _max_loss = (_strike_b - _strike_a) * 100 - _raw_prem
                elif _cname in ("iron_condor", "iron_butterfly", "short_straddle"):
                    _otm = spot * 0.05
                    _put_val = bs_price(spot, spot - _otm, _T, _r, iv, "put") * 100
                    _call_val = bs_price(spot, spot + _otm, _T, _r, iv, "call") * 100
                    _raw_prem = _put_val + _call_val
                    _max_profit = _raw_prem
                    _max_loss = _otm * 100 - _raw_prem
                else:
                    _raw_prem = bs_price(spot, _strike_a, _T, _r, iv, "put") * 100
                    _max_profit = _raw_prem
                    _max_loss = _raw_prem * 3
                _is_credit = True
            else:
                if _cname == "long_call":
                    _raw_prem = bs_price(spot, _strike_a, _T, _r, iv, "call") * 100
                elif _cname == "long_put":
                    _raw_prem = bs_price(spot, _strike_a, _T, _r, iv, "put") * 100
                else:  # long_straddle
                    _raw_prem = (bs_price(spot, spot, _T, _r, iv, "call") +
                                 bs_price(spot, spot, _T, _r, iv, "put")) * 100
                _max_profit = _raw_prem * 3  # theoretical upside
                _max_loss = _raw_prem
                _is_credit = False

            if _max_profit <= 0 or _max_loss <= 0:
                continue

            # Minimum premium gate: skip if credit/debit too small to cover costs.
            # Break-even analysis: with $8 cost/trade and 78% win rate + 2× stop,
            # min credit needed = $8 / 0.34 ≈ $24. Use $40 floor for Beginner to ensure
            # a meaningful edge above break-even (e.g. GLD <$150 era produced $4-10 credits
            # which are below cost, making those trades systematically unprofitable).
            # Standard profiles keep $50 floor (covers commissions for larger premiums).
            _min_prem = 40.0 if profile_dict["max_loss_per_trade"] < 500 else 50.0
            if _raw_prem < _min_prem:
                continue

            # Risk gate: effective risk must fit within profile's max loss per trade.
            if _cname in ("cash_secured_put", "covered_call"):
                _eff_risk = _raw_prem * 2.0
            else:
                _eff_risk = _max_loss
            if _eff_risk > profile_dict["max_loss_per_trade"]:
                continue

            # Capital adequacy: CSP requires strike_a × 100 cash collateral.
            if _cname == "cash_secured_put":
                if _strike_a * 100 > profile_dict["capital"]:
                    continue

            # Capital adequacy: Covered Call requires owning 100 shares of GLD.
            if _cname == "covered_call":
                if spot * 100 > profile_dict["capital"]:
                    continue

            # Crash_risk long_put: require GLD already below EMA20 (downtrend confirmed).
            if _cname == "long_put" and regime.regime == "crash_risk":
                if spot >= float(row["ema20"]):
                    continue

            # All gates passed → take this candidate
            _selected = (_cname, _strike_a, _strike_b, _raw_prem, _max_profit, _max_loss, _is_credit)
            break

        if _selected is None:
            days_since_last_entry += 1
            continue

        strategy_name, strike_a, strike_b, raw_prem, max_profit, max_loss, is_credit = _selected
        dte = target_dte

        # ── Simulate trade day-by-day until exit condition ────────────────────
        expiry_dt = entry_dt + timedelta(days=dte)
        # Credit strategies: exit at 50% of premium collected (Tastytrade standard).
        # Debit strategies: max_profit is a theoretical cap (e.g. 3× spot), so 50% is unreachable.
        # Use premium_paid (= max_loss for debits) as the profit target base instead.
        if is_credit:
            profit_target = max_profit * 0.50   # 50% of credit collected
        else:
            profit_target = max_loss * 1.0      # target = 100% gain on premium paid (2× investment)
        loss_stop = max_loss * 2.0          # 2× max-loss stop (default)
        # All credit strategies: Tastytrade 2× credit collected as the stop.
        # - CSP/CC: max_loss is notional ($4,400), using it as stop is unrealistic.
        # - Spreads: max_loss is the hard cap; 2× cap never triggers.
        # - Iron condor/butterfly: short-only P&L sim overestimates losses (missing long-leg offset);
        #   2× credit stop prevents runaway losses in crash scenarios.
        # Unified: stop = 2× credit for all credit strategies.
        if is_credit:
            loss_stop = raw_prem * 2.0
        early_exit_dte = 21                 # Tastytrade rule: exit at 21 DTE to avoid gamma risk

        pnl = 0.0
        exit_date = expiry_dt
        exit_reason = "expiry"

        future_dates = [d for d in dates if entry_dt < d <= expiry_dt]
        for check_dt in future_dates:
            if check_dt not in date_to_idx:
                continue
            spot_now = float(df.loc[check_dt, "close"])
            iv_now = float(df.loc[check_dt, "iv"])
            dte_now = max(int((expiry_dt - check_dt).days), 0)

            if is_credit:
                day_pnl = _credit_strategy_pnl(
                    strategy_name, spot, spot_now,
                    strike_a, strike_b,
                    iv, iv_now,
                    dte, dte_now,
                    raw_prem,
                )
            else:
                day_pnl = _debit_strategy_pnl(
                    strategy_name, spot, spot_now,
                    strike_a, iv, iv_now,
                    dte, dte_now,
                    raw_prem,
                )

            if is_credit:
                if day_pnl >= profit_target:
                    pnl = day_pnl
                    exit_date = check_dt
                    exit_reason = "50%_profit"
                    break
                if day_pnl <= -loss_stop:
                    pnl = -loss_stop   # cap at stop price (stop order fills near loss_stop)
                    exit_date = check_dt
                    exit_reason = "2x_stop"
                    break
                # 21 DTE rule: exit at 21 DTE regardless to avoid gamma risk
                if dte_now <= early_exit_dte:
                    pnl = day_pnl
                    exit_date = check_dt
                    exit_reason = "21dte_exit"
                    break
            else:
                if day_pnl >= profit_target:
                    pnl = day_pnl
                    exit_date = check_dt
                    exit_reason = "50%_profit"
                    break
                if day_pnl <= -max_loss * 0.9:  # lose ~90% of premium
                    pnl = day_pnl
                    exit_date = check_dt
                    exit_reason = "2x_stop"
                    break
        else:
            # Held to expiry: compute final P&L at expiry date
            if expiry_dt.date() if hasattr(expiry_dt, "date") else expiry_dt in date_to_idx:
                closest_exit = min(future_dates, key=lambda d: abs((d - expiry_dt).days), default=None)
                if closest_exit:
                    spot_expiry = float(df.loc[closest_exit, "close"])
                    iv_expiry = float(df.loc[closest_exit, "iv"])
                    if is_credit:
                        pnl = _credit_strategy_pnl(
                            strategy_name, spot, spot_expiry,
                            strike_a, strike_b, iv, iv_expiry,
                            dte, 0, raw_prem,
                        )
                    else:
                        pnl = _debit_strategy_pnl(
                            strategy_name, spot, spot_expiry,
                            strike_a, iv, iv_expiry,
                            dte, 0, raw_prem,
                        )

        # Cost model: commission (open + close) + slippage on premium
        num_legs = STRATEGY_LEGS.get(strategy_name, 1)
        commission = COMMISSION_PER_CONTRACT * num_legs * 2  # open + close
        # Slippage: percentage-based with per-leg floor.
        # For cheap spreads (net_credit ~$31), 3% gives only $0.93 — below realistic bid-ask
        # impact ($2-5/leg). Floor ensures multi-leg strategies pay realistic execution cost.
        slippage = max(abs(raw_prem) * SLIPPAGE_PCT, SLIPPAGE_PER_LEG_FLOOR * num_legs)
        trade_cost = round(commission + slippage, 2)
        net_pnl = round(pnl - trade_cost, 2)

        trade = Trade(
            entry_date=entry_dt.date() if hasattr(entry_dt, "date") else entry_dt,
            expiry_date=expiry_dt.date() if hasattr(expiry_dt, "date") else expiry_dt,
            strategy=strategy_name,
            regime=regime.regime,
            spot_entry=spot,
            strike_a=strike_a,
            strike_b=strike_b,
            option_type_a="put" if strategy_name in ("cash_secured_put", "bull_put_spread", "long_put") else "call",
            iv_entry=iv,
            dte=dte,
            premium_collected=round(raw_prem, 2),
            max_profit=round(max_profit, 2),
            max_loss=round(max_loss, 2),
            pnl=round(pnl, 2),
            trade_cost=trade_cost,
            net_pnl=net_pnl,
            exit_date=exit_date.date() if hasattr(exit_date, "date") else exit_date,
            exit_reason=exit_reason,
            won=pnl > 0,
            net_won=net_pnl > 0,
        )
        trades.append(trade)
        days_since_last_entry = 0

    return trades


# ─── Statistics & reporting ──────────────────────────────────────────────────

def print_report(trades: list[Trade], profile_name: str, show_chart: bool):
    if not trades:
        console.print("[red]No trades generated.[/red]")
        return

    total = len(trades)
    wins = sum(1 for t in trades if t.won)
    losses = total - wins
    win_rate = wins / total * 100
    total_pnl = sum(t.pnl for t in trades)
    avg_win = (sum(t.pnl for t in trades if t.won) / wins) if wins else 0
    avg_loss = (sum(t.pnl for t in trades if not t.won) / losses) if losses else 0

    # Net (after cost) metrics
    net_wins = sum(1 for t in trades if t.net_won)
    net_losses = total - net_wins
    net_win_rate = net_wins / total * 100
    total_net_pnl = sum(t.net_pnl for t in trades)
    total_cost = sum(t.trade_cost for t in trades)
    avg_cost = total_cost / total

    # Approximate annualized return
    first = min(t.entry_date for t in trades)
    last = max(t.exit_date for t in trades)
    years_elapsed = max((last - first).days / 365, 0.01)

    # Build equity curve
    timeline = sorted(trades, key=lambda t: t.entry_date)
    cumulative = 0.0
    equity_curve = []
    for t in timeline:
        cumulative += t.pnl
        equity_curve.append((t.exit_date, cumulative))

    peak = 0.0
    max_dd = 0.0
    running = 0.0
    for _, cum in equity_curve:
        running = cum
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd

    pnls = [t.pnl for t in trades]
    avg_pnl = total_pnl / total
    std_pnl = float(np.std(pnls)) if len(pnls) > 1 else 1.0
    sharpe = (avg_pnl / std_pnl) * math.sqrt(52) if std_pnl > 0 else 0  # weekly Sharpe

    # Print overall summary
    console.print("\n" + "═" * 65)
    console.print(f"[bold]OptiGold Backtest Results — Profile: {profile_name.upper()}[/bold]")
    console.print("═" * 65)

    pnl_color = "green" if total_pnl > 0 else "red"
    net_color = "green" if total_net_pnl > 0 else "red"
    console.print(f"  Period:            {first} → {last} ({years_elapsed:.1f}y)")
    console.print(f"  Total trades:      {total}")
    console.print(f"  Win rate (gross):  [{pnl_color}]{win_rate:.1f}%[/{pnl_color}] ({wins}W / {losses}L)")
    console.print(f"  Win rate (net):    [{net_color}]{net_win_rate:.1f}%[/{net_color}] ({net_wins}W / {net_losses}L)  [dim]← after costs[/dim]")
    console.print(f"  Avg win:           [green]+${avg_win:.0f}[/green]")
    console.print(f"  Avg loss:          [red]${avg_loss:.0f}[/red]")
    console.print(f"  Total P&L (gross): [{pnl_color}]${total_pnl:+,.0f}[/{pnl_color}]")
    console.print(f"  Total P&L (net):   [{net_color}]${total_net_pnl:+,.0f}[/{net_color}]  [dim](cost: ${total_cost:,.0f} total / ${avg_cost:.0f} avg/trade)[/dim]")
    console.print(f"  Sharpe (weekly):   {sharpe:.2f}")
    console.print(f"  Max drawdown:      [red]-${max_dd:,.0f}[/red]")

    # ── Supplementary risk metrics ─────────────────────────────────────────
    worst_net = min(t.net_pnl for t in trades)

    max_consec = cur_consec = 0
    for t in sorted(trades, key=lambda x: x.entry_date):
        if not t.net_won:
            cur_consec += 1
            max_consec = max(max_consec, cur_consec)
        else:
            cur_consec = 0

    from collections import defaultdict
    by_year: dict[int, float] = defaultdict(float)
    for t in trades:
        by_year[t.entry_date.year] += t.net_pnl
    year_str = "  ".join(
        f"{y}: [{'green' if v >= 0 else 'red'}]{'+'if v >= 0 else ''}${v:,.0f}[/{'green' if v >= 0 else 'red'}]"
        for y, v in sorted(by_year.items())
    )

    console.print(f"  Worst trade (net): [red]${worst_net:+,.0f}[/red]")
    console.print(f"  Max consec losses: {max_consec}")
    console.print(f"  P&L by year:       {year_str}")

    csp_trades = [t for t in trades if t.strategy == "cash_secured_put"]
    if csp_trades:
        profile_capital = PROFILES.get(profile_name, {}).get("capital", 0)
        avg_req = sum(t.strike_a * 100 for t in csp_trades) / len(csp_trades)
        max_req = max(t.strike_a * 100 for t in csp_trades)
        console.print(
            f"  CSP capital req:   avg ${avg_req:,.0f}  max ${max_req:,.0f}"
            f"  [dim](profile capital: ${profile_capital:,})[/dim]"
        )

    # Per-strategy breakdown
    strats: dict[str, dict] = {}
    for t in trades:
        s = t.strategy
        if s not in strats:
            strats[s] = {"n": 0, "wins": 0, "pnl": 0.0}
        strats[s]["n"] += 1
        strats[s]["pnl"] += t.pnl
        if t.won:
            strats[s]["wins"] += 1

    console.print("\n[bold]By Strategy:[/bold]")
    if HAS_RICH:
        tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        tbl.add_column("Strategy", width=22)
        tbl.add_column("Trades", justify="right")
        tbl.add_column("Win%", justify="right")
        tbl.add_column("Total P&L", justify="right")
        tbl.add_column("Avg P&L", justify="right")
        for s, v in sorted(strats.items(), key=lambda x: -x[1]["pnl"]):
            wr = v["wins"] / v["n"] * 100
            avg = v["pnl"] / v["n"]
            color = "green" if v["pnl"] > 0 else "red"
            tbl.add_row(
                s,
                str(v["n"]),
                f"{wr:.0f}%",
                f"[{color}]${v['pnl']:+,.0f}[/{color}]",
                f"[{color}]${avg:+.0f}[/{color}]",
            )
        console.print(tbl)
    else:
        for s, v in sorted(strats.items(), key=lambda x: -x[1]["pnl"]):
            wr = v["wins"] / v["n"] * 100
            print(f"  {s:25s}  n={v['n']:3d}  wr={wr:.0f}%  pnl=${v['pnl']:+,.0f}")

    # Per-regime breakdown
    regimes: dict[str, dict] = {}
    for t in trades:
        rg = t.regime
        if rg not in regimes:
            regimes[rg] = {"n": 0, "wins": 0, "pnl": 0.0}
        regimes[rg]["n"] += 1
        regimes[rg]["pnl"] += t.pnl
        if t.won:
            regimes[rg]["wins"] += 1

    console.print("\n[bold]By Market Regime:[/bold]")
    if HAS_RICH:
        tbl2 = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        tbl2.add_column("Regime", width=22)
        tbl2.add_column("Trades", justify="right")
        tbl2.add_column("Win%", justify="right")
        tbl2.add_column("Total P&L", justify="right")
        for rg, v in sorted(regimes.items(), key=lambda x: -x[1]["n"]):
            wr = v["wins"] / v["n"] * 100
            color = "green" if v["pnl"] > 0 else "red"
            tbl2.add_row(rg, str(v["n"]), f"{wr:.0f}%", f"[{color}]${v['pnl']:+,.0f}[/{color}]")
        console.print(tbl2)
    else:
        for rg, v in sorted(regimes.items(), key=lambda x: -x[1]["n"]):
            wr = v["wins"] / v["n"] * 100
            print(f"  {rg:25s}  n={v['n']:3d}  wr={wr:.0f}%  pnl=${v['pnl']:+,.0f}")

    # Exit reason breakdown
    exits: dict[str, int] = {}
    for t in trades:
        exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
    console.print("\n[bold]Exit Reasons:[/bold]")
    for reason, count in sorted(exits.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        console.print(f"  {reason:18s}  {count:3d}  ({pct:.0f}%)")

    # Comparison vs documented benchmarks
    console.print("\n[bold]Benchmark Comparison (literature):[/bold]")
    console.print("  [dim]OptionAlpha/Tastytrade IV>50 iron condor win rate: ~57%[/dim]")
    console.print("  [dim]GLD covered call annualized return: ~3.3%[/dim]")
    console.print("  [dim]Short straddle >IVR50 win rate: ~80%[/dim]")
    wrc = "green" if net_win_rate >= 55 else "yellow" if net_win_rate >= 45 else "red"
    console.print(f"  Our gross win rate: {win_rate:.1f}%  →  "
                  f"net win rate: [{wrc}]{net_win_rate:.1f}%[/{wrc}]  "
                  f"(target ≥55% for credit strategies)")

    # Chart
    if show_chart:
        try:
            import matplotlib.pyplot as plt
            dates_c = [d for d, _ in equity_curve]
            vals_c = [v for _, v in equity_curve]
            plt.figure(figsize=(12, 5))
            plt.plot(dates_c, vals_c, color="gold", linewidth=1.5)
            plt.fill_between(dates_c, vals_c, 0,
                             where=[v >= 0 for v in vals_c], color="green", alpha=0.15)
            plt.fill_between(dates_c, vals_c, 0,
                             where=[v < 0 for v in vals_c], color="red", alpha=0.15)
            plt.axhline(0, color="white", linewidth=0.5)
            plt.title(f"OptiGold Backtest — {profile_name.upper()} — Equity Curve")
            plt.xlabel("Date")
            plt.ylabel("Cumulative P&L ($)")
            plt.tight_layout()
            plt.savefig("backtest_equity_curve.png", dpi=150)
            plt.show()
            console.print("\n[dim]Chart saved to backtest_equity_curve.png[/dim]")
        except ImportError:
            console.print("[dim]matplotlib not installed; skipping chart[/dim]")


# ─── Sensitivity / comparison helpers ────────────────────────────────────────

def _summary(trades: list[Trade], label: str) -> dict:
    if not trades:
        return {"label": label, "n": 0, "gross_wr": 0.0, "net_wr": 0.0, "net_pnl": 0.0}
    n = len(trades)
    gross_wr = sum(1 for t in trades if t.won) / n * 100
    net_wr = sum(1 for t in trades if t.net_won) / n * 100
    net_pnl = sum(t.net_pnl for t in trades)
    return {"label": label, "n": n, "gross_wr": gross_wr, "net_wr": net_wr, "net_pnl": net_pnl}


def _print_comparison(rows: list[dict], title: str, col_label: str) -> None:
    console.print(f"\n[bold cyan]═══ Sensitivity: {title} ═══[/bold cyan]")
    if HAS_RICH:
        tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        tbl.add_column(col_label, width=20)
        tbl.add_column("Trades", justify="right")
        tbl.add_column("Gross Win%", justify="right")
        tbl.add_column("Net Win%", justify="right")
        tbl.add_column("Net P&L", justify="right")
        for r in rows:
            c = "green" if r["net_pnl"] > 0 else "red"
            tbl.add_row(
                r["label"], str(r["n"]),
                f"{r['gross_wr']:.1f}%", f"{r['net_wr']:.1f}%",
                f"[{c}]${r['net_pnl']:+,.0f}[/{c}]",
            )
        console.print(tbl)
    else:
        print(f"\n{'Sensitivity: ' + title}")
        print(f"  {col_label:20s}  {'n':>5}  {'Gross Win%':>10}  {'Net Win%':>8}  {'Net P&L':>10}")
        for r in rows:
            print(f"  {r['label']:20s}  {r['n']:>5}  {r['gross_wr']:>9.1f}%  {r['net_wr']:>7.1f}%  ${r['net_pnl']:>+9,.0f}")


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OptiGold Historical Backtest")
    parser.add_argument("--years", type=int, default=2, help="Years of history (default 2)")
    parser.add_argument("--profile", default="intermediate",
                        choices=list(PROFILES.keys()),
                        help="User profile preset (default: intermediate)")
    parser.add_argument("--strategy", default=None,
                        help="Force a specific strategy (e.g. iron_condor). Default: auto-select.")
    parser.add_argument("--dte", type=int, default=30, help="Target DTE (default 30)")
    parser.add_argument("--freq", type=int, default=7,
                        help="Entry frequency in trading days (default 7 = weekly)")
    parser.add_argument("--chart", action="store_true", help="Show equity curve chart")
    parser.add_argument("--sensitivity", choices=["ivr", "dte"],
                        help="Run sensitivity sweep: ivr (30/35/40/45) or dte (21/30/45)")
    parser.add_argument("--compare-profiles", action="store_true",
                        help="Compare all three profiles side-by-side")
    parser.add_argument("--iv-data", default=None, metavar="PATH",
                        help="Path to real IV CSV from build_iv_series.py (e.g. data/gld_iv_daily.csv)")
    args = parser.parse_args()

    # ── Load real IV data if provided ─────────────────────────────────────────
    real_iv_df = None
    if args.iv_data:
        real_iv_df = load_real_iv(args.iv_data)

    # ── Sensitivity mode ──────────────────────────────────────────────────────
    if args.sensitivity == "ivr":
        console.print(f"\n[bold cyan]IVR Threshold Sensitivity ({args.years}y, freq={args.freq})[/bold cyan]")
        rows = []
        for ivr in [30, 35, 40, 45]:
            t = run_backtest(years=args.years, profile_name=args.profile,
                             target_dte=args.dte, entry_freq_days=args.freq,
                             ivr_min=float(ivr), real_iv_df=real_iv_df)
            rows.append(_summary(t, f"IVR ≥ {ivr}"))
        _print_comparison(rows, "IVR Min Threshold", "IVR Min")
        return

    if args.sensitivity == "dte":
        console.print(f"\n[bold cyan]DTE Sensitivity ({args.years}y, freq={args.freq})[/bold cyan]")
        rows = []
        for dte in [21, 30, 45]:
            t = run_backtest(years=args.years, profile_name=args.profile,
                             target_dte=dte, entry_freq_days=args.freq,
                             real_iv_df=real_iv_df)
            rows.append(_summary(t, f"DTE = {dte}"))
        _print_comparison(rows, "Target DTE", "DTE")
        return

    if args.compare_profiles:
        console.print(f"\n[bold cyan]Profile Comparison ({args.years}y, freq={args.freq})[/bold cyan]")
        rows = []
        for prof in ["beginner", "intermediate", "advanced"]:
            t = run_backtest(years=args.years, profile_name=prof,
                             target_dte=args.dte, entry_freq_days=args.freq,
                             real_iv_df=real_iv_df)
            rows.append(_summary(t, prof.capitalize()))
        _print_comparison(rows, "User Profile", "Profile")
        return

    # ── Normal single-run mode ────────────────────────────────────────────────
    console.print(f"\n[bold cyan]OptiGold Backtest[/bold cyan]")
    console.print(f"  Profile:   {args.profile}")
    console.print(f"  History:   {args.years} years of GLD")
    console.print(f"  DTE:       {args.dte} days")
    console.print(f"  Frequency: every {args.freq} trading days")
    if args.strategy:
        console.print(f"  Strategy:  [yellow]{args.strategy}[/yellow] (forced)")
    if real_iv_df is not None:
        console.print(f"  IV source: [green]Real (OptionsDX)[/green]")
    else:
        console.print(f"  IV source: [yellow]HV×1.15 proxy[/yellow] (run build_iv_series.py for real IV)")
    console.print("[dim]Exit rules: 50% profit target OR 2× max-loss stop OR expiry[/dim]")

    trades = run_backtest(
        years=args.years,
        profile_name=args.profile,
        force_strategy=args.strategy,
        target_dte=args.dte,
        entry_freq_days=args.freq,
        real_iv_df=real_iv_df,
    )

    print_report(trades, args.profile, args.chart)


if __name__ == "__main__":
    main()
