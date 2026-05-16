from __future__ import annotations

"""
Market data service — Phase 2: Live Alpaca data.

Fetches real GLD price, historical bars (for EMA/RSI/ADX/HV),
and options chain snapshots (with Greeks + IV) from Alpaca.
Falls back to synthetic data when market is closed or API errors occur.
"""

import math
import random
from datetime import datetime, date, timedelta
from typing import Optional

import numpy as np
import pytz

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest,
    StockLatestQuoteRequest,
    OptionChainRequest,
    OptionSnapshotRequest,
)
from alpaca.data.timeframe import TimeFrame

from app.core.alpaca_client import get_stock_data_client, get_option_data_client
from app.quant.iv_analysis import (
    iv_rank as compute_iv_rank,
    iv_percentile as compute_iv_percentile,
    historical_volatility,
    iv_premium_ratio,
)
from app.quant.market_regime import detect_regime, MarketRegime
from app.utils.market_hours import get_market_session, now_eastern
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# ── Fallback synthetic baseline (used when API unavailable) ──────────────────
_BASE_GLD_PRICE = 220.50
_BASE_ATM_IV = 0.155
_BASE_HV_20D = 0.130
_BASE_VIX = 18.5
_RNG = random.Random()


# ── Technical indicator helpers ──────────────────────────────────────────────

def _ema(prices: list[float], period: int) -> float:
    """Exponential moving average of the last `period` values."""
    if len(prices) < period:
        return float(np.mean(prices))
    k = 2.0 / (period + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p * k + ema * (1 - k)
    return round(ema, 4)


def _rsi(prices: list[float], period: int = 14) -> float:
    """Wilder RSI."""
    if len(prices) < period + 1:
        return 50.0
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(d, 0) for d in deltas[-period:]]
    losses = [abs(min(d, 0)) for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 1)


def _adx(closes: list[float], highs: list[float], lows: list[float], period: int = 14) -> float:
    """Simplified ADX approximation using True Range."""
    if len(closes) < period + 1:
        return 20.0
    trs = []
    for i in range(1, len(closes)):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        trs.append(max(hl, hc, lc))
    atr = sum(trs[-period:]) / period
    if atr == 0:
        return 20.0
    # Use price range as proxy for directional movement
    recent_closes = closes[-period:]
    up_move = recent_closes[-1] - recent_closes[0]
    adx_proxy = min(abs(up_move) / atr * 25, 60.0)
    return round(adx_proxy, 1)


# ── Alpaca data fetchers ──────────────────────────────────────────────────────

def _fetch_vix() -> float:
    """Fetch latest VIX close from yfinance. Falls back to 20.0 on any error."""
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="2d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception as e:
        logger.debug("VIX fetch failed: %s", e)
    return 20.0


def _fetch_gld_bars(lookback_days: int = 60) -> Optional[dict]:
    """Fetch daily GLD bars from Alpaca. Returns None on failure."""
    try:
        client: StockHistoricalDataClient = get_stock_data_client()
        start = datetime.now(pytz.UTC) - timedelta(days=lookback_days + 10)
        req = StockBarsRequest(
            symbol_or_symbols="GLD",
            timeframe=TimeFrame.Day,
            start=start,
            limit=lookback_days + 10,
        )
        bars = client.get_stock_bars(req)
        gld_bars = bars.data.get("GLD", []) if hasattr(bars, "data") else bars["GLD"]
        if not gld_bars:
            return None

        closes = [b.close for b in gld_bars]
        highs = [b.high for b in gld_bars]
        lows = [b.low for b in gld_bars]
        volumes = [b.volume for b in gld_bars]

        return {
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
            "latest_close": closes[-1],
            "prev_close": closes[-2] if len(closes) > 1 else closes[-1],
        }
    except Exception as e:
        logger.warning("Failed to fetch GLD bars: %s", e)
        return None


def _fetch_gld_latest_quote() -> Optional[float]:
    """Fetch latest GLD quote (ask price). Returns None on failure."""
    try:
        client = get_stock_data_client()
        req = StockLatestQuoteRequest(symbol_or_symbols="GLD")
        quote = client.get_stock_latest_quote(req)
        gld_quote = quote.get("GLD")
        if gld_quote:
            ask = gld_quote.ask_price or 0.0
            bid = gld_quote.bid_price or 0.0
            # Use mid if both available, ask if only ask, bid if only bid
            if ask > 0 and bid > 0:
                return float((ask + bid) / 2)
            elif ask > 0:
                return float(ask)
            elif bid > 0:
                return float(bid)
        return None
    except Exception as e:
        logger.warning("Failed to fetch GLD quote: %s", e)
        return None


def _fetch_options_chain(symbol: str = "GLD") -> list[dict]:
    """
    Fetch GLD options chain snapshot from Alpaca.
    Returns a list of option dicts with Greeks and IV.
    """
    try:
        client: OptionHistoricalDataClient = get_option_data_client()

        # Request options expiring in next 90 days
        expiry_min = date.today() + timedelta(days=14)
        expiry_max = date.today() + timedelta(days=90)

        req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=expiry_min,
            expiration_date_lte=expiry_max,
        )
        chain = client.get_option_chain(req)

        result = []
        for symbol_key, snapshot in chain.items():
            try:
                greeks = snapshot.greeks
                if greeks is None or snapshot.implied_volatility is None:
                    continue

                quote = snapshot.latest_quote

                # Parse option symbol: e.g. GLD260410C00465000
                # Format: UNDERLYING + YYMMDD + C/P + 8-digit strike (×1000)
                raw = symbol_key[len(symbol):]          # e.g. "260410C00465000"
                exp_str = raw[:6]                        # "260410"
                opt_char = raw[6]                        # "C" or "P"
                strike_str = raw[7:]                     # "00465000"

                opt_type = "call" if opt_char == "C" else "put"
                strike = float(strike_str) / 1000.0
                expiry_date = date(
                    2000 + int(exp_str[:2]),
                    int(exp_str[2:4]),
                    int(exp_str[4:6]),
                )

                bid = float(quote.bid_price) if quote and quote.bid_price else 0.0
                ask = float(quote.ask_price) if quote and quote.ask_price else 0.0
                mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0.0

                result.append({
                    "symbol": symbol_key,
                    "type": opt_type,
                    "strike": strike,
                    "expiry": expiry_date,
                    "dte": (expiry_date - date.today()).days,
                    "bid": bid,
                    "ask": ask,
                    "mid": mid,
                    "delta": float(greeks.delta) if greeks.delta is not None else 0.0,
                    "gamma": float(greeks.gamma) if greeks.gamma is not None else 0.0,
                    "theta": float(greeks.theta) if greeks.theta is not None else 0.0,
                    "vega": float(greeks.vega) if greeks.vega is not None else 0.0,
                    "iv": float(snapshot.implied_volatility),
                })
            except Exception:
                continue

        logger.info("Fetched %d option contracts for %s", len(result), symbol)
        return result

    except Exception as e:
        logger.warning("Failed to fetch options chain for %s: %s", symbol, e)
        return []


def _compute_atm_iv(options_chain: list[dict], gld_price: float) -> float:
    """Find ATM IV from the options chain."""
    if not options_chain:
        return _BASE_ATM_IV

    calls = [o for o in options_chain if o["type"] == "call" and o["iv"] > 0]
    if not calls:
        return _BASE_ATM_IV

    # Find call closest to ATM
    atm_call = min(calls, key=lambda o: abs(o["strike"] - gld_price))
    return atm_call["iv"]


# ── IV history (using 1-year of daily bar-derived HV as proxy) ───────────────

def _build_iv_history_from_bars(closes: list[float]) -> list[float]:
    """
    Construct a proxy IV history from rolling 20-day HV windows.
    Real IV history requires premium data; HV × 1.15 is a common estimate.
    """
    iv_series = []
    for i in range(20, len(closes)):
        window = closes[i - 20:i + 1]
        log_returns = [math.log(window[j] / window[j - 1]) for j in range(1, len(window))]
        hv = float(np.std(log_returns)) * math.sqrt(252)
        # IV typically trades at ~10-20% premium to HV
        iv_series.append(round(hv * 1.15, 4))
    return iv_series if iv_series else [_BASE_ATM_IV] * 50


# ── Synthetic fallback ────────────────────────────────────────────────────────

def _synthetic_snapshot(gld_price: Optional[float] = None) -> dict:
    """Return synthetic snapshot when live data unavailable."""
    price = gld_price or round(_BASE_GLD_PRICE + _RNG.gauss(0, 0.8), 2)
    atm_iv = round(_BASE_ATM_IV + _RNG.gauss(0, 0.005), 4)
    hv_20d = round(_BASE_HV_20D + _RNG.gauss(0, 0.003), 4)
    atm_iv = max(0.06, min(0.55, atm_iv))
    hv_20d = max(0.05, min(0.50, hv_20d))

    iv_hist = [_BASE_ATM_IV + _RNG.gauss(0, 0.01) for _ in range(252)]
    ivr = compute_iv_rank(atm_iv, iv_hist)
    ivp = compute_iv_percentile(atm_iv, iv_hist)
    iv_prem = iv_premium_ratio(atm_iv, hv_20d)

    return {
        "captured_at": datetime.utcnow(),
        "gld_price": price,
        "gld_24h_change_pct": round(_RNG.gauss(0.05, 0.35), 2),
        "gld_atm_iv": atm_iv,
        "gld_iv_rank": round(ivr, 1),
        "gld_iv_percentile": round(ivp, 1),
        "gld_hv_20d": hv_20d,
        "vix_level": round(_BASE_VIX + _RNG.gauss(0, 0.5), 2),
        "iv_premium_ratio": round(iv_prem, 3),
        "put_call_skew": round(_RNG.gauss(1.5, 0.3), 2),
        "ema20": round(price * 0.992, 2),
        "ema50": round(price * 0.978, 2),
        "rsi_14": round(_RNG.gauss(52, 5), 1),
        "adx": round(_RNG.gauss(22, 4), 1),
        "market_session": get_market_session(now_eastern()),
        "_data_source": "synthetic",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def get_gld_snapshot() -> dict:
    """
    Main entry point. Returns a GLD market snapshot dict.
    Uses live Alpaca data; falls back to synthetic on error or market close.
    """
    now_et = now_eastern()
    session = get_market_session(now_et)

    # --- Step 1: Fetch historical bars (needed for technicals + HV) ---
    bars = _fetch_gld_bars(lookback_days=252)

    if bars is None:
        logger.warning("No bar data — using synthetic snapshot")
        snap = _synthetic_snapshot()
        regime = detect_regime(snap)
        snap["market_regime"] = regime.regime
        snap["regime_confidence"] = round(regime.confidence, 3)
        return snap

    closes = bars["closes"]
    highs = bars["highs"]
    lows = bars["lows"]

    # --- Step 2: Latest price (live quote or last close) ---
    live_price = _fetch_gld_latest_quote()
    gld_price = live_price if live_price and live_price > 0 else bars["latest_close"]
    prev_close = bars["prev_close"]
    change_pct = round((gld_price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0.0

    # --- Step 3: Technical indicators from bars ---
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    rsi = _rsi(closes, 14)
    adx = _adx(closes, highs, lows, 14)
    hv_20d = round(historical_volatility(closes, window=20), 4)  # already decimal (e.g. 0.28 = 28%)

    # --- Step 4: Options chain + IV ---
    options_chain = _fetch_options_chain("GLD")
    atm_iv = _compute_atm_iv(options_chain, gld_price)
    if atm_iv <= 0:
        atm_iv = max(hv_20d * 1.15, 0.08)

    # --- Step 5: IV Rank from HV-proxy history ---
    iv_hist = _build_iv_history_from_bars(closes)
    ivr = compute_iv_rank(atm_iv, iv_hist)
    ivp = compute_iv_percentile(atm_iv, iv_hist)
    iv_prem = iv_premium_ratio(atm_iv, hv_20d)

    # Put/call skew: average put IV vs call IV near ATM
    atm_puts = [o for o in options_chain
                if o["type"] == "put" and abs(o["strike"] - gld_price) / gld_price < 0.05 and o["iv"] > 0]
    atm_calls = [o for o in options_chain
                 if o["type"] == "call" and abs(o["strike"] - gld_price) / gld_price < 0.05 and o["iv"] > 0]
    if atm_puts and atm_calls:
        avg_put_iv = sum(o["iv"] for o in atm_puts) / len(atm_puts)
        avg_call_iv = sum(o["iv"] for o in atm_calls) / len(atm_calls)
        put_call_skew = round(avg_put_iv / avg_call_iv, 3) if avg_call_iv > 0 else 1.0
    else:
        put_call_skew = 1.0

    snapshot = {
        "captured_at": datetime.utcnow(),
        "gld_price": round(gld_price, 2),
        "gld_24h_change_pct": change_pct,
        "gld_atm_iv": round(atm_iv, 4),
        "gld_iv_rank": round(ivr, 1),
        "gld_iv_percentile": round(ivp, 1),
        "gld_hv_20d": round(hv_20d, 4),
        "vix_level": _fetch_vix(),   # yfinance fallback (Alpaca free tier lacks VIX)
        "iv_premium_ratio": round(iv_prem, 3),
        "put_call_skew": put_call_skew,
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "rsi_14": rsi,
        "adx": adx,
        "market_session": session,
        "_data_source": "alpaca_live" if live_price else "alpaca_bars",
        "_options_count": len(options_chain),
    }

    regime: MarketRegime = detect_regime(snapshot)
    snapshot["market_regime"] = regime.regime
    snapshot["regime_confidence"] = round(regime.confidence, 3)

    logger.info(
        "GLD snapshot: price=%.2f IV=%.1f%% IVR=%.0f regime=%s source=%s opts=%d",
        gld_price, atm_iv * 100, ivr, regime.regime,
        snapshot["_data_source"], len(options_chain),
    )
    return snapshot


def get_options_chain(symbol: str = "GLD") -> list[dict]:
    """Return live options chain or empty list."""
    return _fetch_options_chain(symbol)


def get_iv_history(symbol: str = "GLD", lookback_days: int = 252) -> list[float]:
    """
    Return IV history for IV Rank calculation.
    Uses HV-proxy from bar data; falls back to synthetic.
    """
    bars = _fetch_gld_bars(lookback_days=lookback_days + 30)
    if bars:
        return _build_iv_history_from_bars(bars["closes"])
    return [_BASE_ATM_IV + _RNG.gauss(0, 0.01) for _ in range(lookback_days)]
