from __future__ import annotations

"""Implied Volatility analysis utilities."""

import math
from typing import Sequence

import numpy as np


def iv_rank(current_iv: float, iv_history: Sequence[float]) -> float:
    """
    IV Rank: where does current IV sit in the 52-week high/low range?

    Formula: (current_iv - iv_min) / (iv_max - iv_min) * 100

    Returns:
        Float in [0, 100].  Returns 50.0 if history is empty or flat.
    """
    if not iv_history:
        return 50.0
    iv_min = min(iv_history)
    iv_max = max(iv_history)
    if math.isclose(iv_max, iv_min, rel_tol=1e-9):
        return 50.0
    rank = (current_iv - iv_min) / (iv_max - iv_min) * 100.0
    return float(max(0.0, min(100.0, rank)))


def iv_percentile(current_iv: float, iv_history: Sequence[float]) -> float:
    """
    IV Percentile: fraction of past observations below current IV.

    Returns:
        Float in [0, 100].  Returns 50.0 if history is empty.
    """
    if not iv_history:
        return 50.0
    below = sum(1 for v in iv_history if v < current_iv)
    return float(below / len(iv_history) * 100.0)


def historical_volatility(prices: Sequence[float], window: int = 20) -> float:
    """
    Annualised historical (realised) volatility using close-to-close log returns.

    Args:
        prices: Time-ordered sequence of closing prices (oldest first).
        window: Rolling window in trading days.

    Returns:
        Annualised HV as a decimal (e.g. 0.15 for 15%).
        Returns 0.0 if insufficient data.
    """
    if len(prices) < 2:
        return 0.0

    arr = np.array(prices, dtype=float)
    log_returns = np.diff(np.log(arr))

    # Use the last *window* returns
    if len(log_returns) >= window:
        log_returns = log_returns[-window:]

    if len(log_returns) < 2:
        return 0.0

    daily_std = float(np.std(log_returns, ddof=1))
    annualised = daily_std * math.sqrt(252)
    return annualised


def iv_premium_ratio(atm_iv: float, hv_20d: float) -> float:
    """
    Ratio of implied volatility to historical volatility.

    Returns:
        IV / HV ratio.  A value > 1 means options are "expensive".
        Returns 1.0 if HV is zero to avoid division errors.
    """
    if hv_20d <= 0:
        return 1.0
    return atm_iv / hv_20d


def iv_environment(iv_rank_value: float) -> str:
    """Classify the IV environment from IV Rank."""
    if iv_rank_value >= 70:
        return "high"
    if iv_rank_value >= 40:
        return "normal"
    return "low"


def skew_direction(put_call_skew: float) -> str:
    """
    Classify put/call skew direction.

    put_call_skew = put_IV - call_IV (same delta magnitude).
    Positive skew means puts are more expensive (bearish fear premium).
    """
    if put_call_skew > 2.0:
        return "bearish_skew"
    if put_call_skew < -2.0:
        return "bullish_skew"
    return "neutral"
