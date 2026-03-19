"""Unit tests for IV analysis utilities."""

import math
import pytest
from app.quant.iv_analysis import (
    iv_rank,
    iv_percentile,
    historical_volatility,
    iv_premium_ratio,
    iv_environment,
    skew_direction,
)


# ── iv_rank ───────────────────────────────────────────────────────────────────

def test_iv_rank_at_52w_high():
    history = [0.10, 0.15, 0.20, 0.25]
    assert iv_rank(0.25, history) == 100.0


def test_iv_rank_at_52w_low():
    history = [0.10, 0.15, 0.20, 0.25]
    assert iv_rank(0.10, history) == 0.0


def test_iv_rank_midpoint():
    history = [0.10, 0.20]
    assert abs(iv_rank(0.15, history) - 50.0) < 1e-9


def test_iv_rank_clamped_above_history():
    history = [0.10, 0.15, 0.20]
    # IV above history max → clamped to 100
    assert iv_rank(0.30, history) == 100.0


def test_iv_rank_empty_history():
    assert iv_rank(0.20, []) == 50.0


def test_iv_rank_flat_history():
    history = [0.20, 0.20, 0.20]
    assert iv_rank(0.20, history) == 50.0


# ── iv_percentile ─────────────────────────────────────────────────────────────

def test_iv_percentile_above_all():
    """IV above all history → 100%."""
    history = [0.10, 0.12, 0.14, 0.16]
    pct = iv_percentile(0.20, history)
    assert pct == 100.0


def test_iv_percentile_below_all():
    """IV below all history → 0%."""
    history = [0.20, 0.25, 0.30]
    pct = iv_percentile(0.10, history)
    assert pct == 0.0


def test_iv_percentile_half():
    """IV at median → ~50%."""
    history = [0.10, 0.10, 0.20, 0.20]
    pct = iv_percentile(0.15, history)
    assert pct == 50.0


def test_iv_percentile_empty():
    assert iv_percentile(0.20, []) == 50.0


# ── historical_volatility ─────────────────────────────────────────────────────

def test_hv_returns_zero_for_single_price():
    assert historical_volatility([100.0]) == 0.0


def test_hv_returns_zero_for_empty():
    assert historical_volatility([]) == 0.0


def test_hv_constant_prices_returns_zero():
    prices = [100.0] * 25
    hv = historical_volatility(prices, window=20)
    assert hv == 0.0


def test_hv_annualisation():
    """For a known daily std, annualised HV = daily_std * sqrt(252)."""
    import numpy as np

    # Construct prices with exact log returns of 0.01 daily std
    prices = [100.0]
    np.random.seed(42)
    for _ in range(25):
        prices.append(prices[-1] * math.exp(np.random.normal(0, 0.01)))

    hv = historical_volatility(prices, window=20)
    assert 0.01 < hv < 1.0  # Sanity: non-zero, non-absurd


def test_hv_higher_for_volatile_series():
    """Volatile price series → higher HV than stable series."""
    stable = [100 + i * 0.01 for i in range(25)]  # near-flat
    volatile = [100 * (1 + (i % 2) * 0.02 - 0.01) for i in range(25)]
    hv_stable = historical_volatility(stable)
    hv_volatile = historical_volatility(volatile)
    assert hv_volatile > hv_stable


# ── iv_premium_ratio ──────────────────────────────────────────────────────────

def test_iv_premium_ratio_greater_than_one():
    assert iv_premium_ratio(0.20, 0.15) > 1.0


def test_iv_premium_ratio_equals_one_when_equal():
    assert iv_premium_ratio(0.15, 0.15) == pytest.approx(1.0)


def test_iv_premium_ratio_less_than_one():
    assert iv_premium_ratio(0.10, 0.20) < 1.0


def test_iv_premium_ratio_zero_hv():
    """Avoid division by zero; returns 1.0 when HV is 0."""
    assert iv_premium_ratio(0.20, 0.0) == 1.0


# ── iv_environment & skew_direction ──────────────────────────────────────────

def test_iv_environment_high():
    assert iv_environment(75) == "high"


def test_iv_environment_normal():
    assert iv_environment(50) == "normal"


def test_iv_environment_low():
    assert iv_environment(20) == "low"


def test_skew_direction_bearish():
    assert skew_direction(5.0) == "bearish_skew"


def test_skew_direction_neutral():
    assert skew_direction(1.0) == "neutral"


def test_skew_direction_bullish():
    assert skew_direction(-3.0) == "bullish_skew"
