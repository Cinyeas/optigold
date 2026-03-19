"""Unit tests for Kelly criterion position sizing."""

import pytest
from app.quant.kelly_sizer import (
    kelly_fraction,
    adjusted_kelly,
    position_size,
    validate_position,
    expected_value,
)


# ── kelly_fraction ────────────────────────────────────────────────────────────

def test_kelly_fraction_positive_edge():
    """60% win prob, 1:1 payoff → Kelly = 0.20."""
    f = kelly_fraction(0.60, 1.0, 1.0)
    assert abs(f - 0.20) < 1e-9


def test_kelly_fraction_no_edge():
    """50% win prob, 1:1 payoff → Kelly = 0 (coin flip)."""
    f = kelly_fraction(0.50, 1.0, 1.0)
    assert f == 0.0


def test_kelly_fraction_strong_edge():
    """70% win, 2:1 payoff → Kelly = (2*0.7 - 0.3) / 2 = 0.55."""
    f = kelly_fraction(0.70, 2.0, 1.0)
    expected = (2.0 * 0.70 - 0.30) / 2.0
    assert abs(f - expected) < 1e-9


def test_kelly_fraction_negative_edge_returns_zero():
    """Negative EV bet → Kelly clamps to 0."""
    f = kelly_fraction(0.30, 1.0, 2.0)
    assert f == 0.0


def test_kelly_fraction_clamped_to_one():
    """Extremely good edge should be clamped to 1."""
    f = kelly_fraction(0.99, 100.0, 1.0)
    assert f <= 1.0


def test_kelly_fraction_zero_loss_returns_zero():
    f = kelly_fraction(0.60, 1.0, 0.0)
    assert f == 0.0


# ── adjusted_kelly ────────────────────────────────────────────────────────────

def test_adjusted_kelly_half_kelly():
    """0.5× multiplier of Kelly 0.20 → 0.10."""
    assert adjusted_kelly(0.20, 0.5) == pytest.approx(0.10)


def test_adjusted_kelly_capped_at_025():
    """Adjusted Kelly must never exceed 0.25."""
    result = adjusted_kelly(0.90, 1.0)
    assert result == 0.25


def test_adjusted_kelly_zero():
    assert adjusted_kelly(0.0, 0.5) == 0.0


def test_adjusted_kelly_full_multiplier():
    assert adjusted_kelly(0.20, 1.0) == pytest.approx(0.20)


# ── position_size ─────────────────────────────────────────────────────────────

def test_position_size_basic():
    """50000 capital, 10% fraction (but 5% cap), 500 risk/unit → 5 contracts."""
    # 5% of 50000 = 2500; 2500 / 500 = 5
    n = position_size(50_000, 0.10, 500)
    assert n == 5


def test_position_size_five_pct_cap():
    """Kelly fraction above 5% is capped at 5% of capital."""
    n = position_size(100_000, 0.25, 500)
    # 5% of 100000 = 5000; 5000 / 500 = 10
    assert n == 10


def test_position_size_zero_capital():
    assert position_size(0, 0.10, 500) == 0


def test_position_size_zero_risk_per_unit():
    assert position_size(50_000, 0.10, 0) == 0


def test_position_size_large_risk_returns_zero():
    """If risk per unit > max risk dollars → 0 contracts."""
    n = position_size(10_000, 0.01, 5_000)
    # 5% of 10000 = 500; min(1000, 500) = 500; 500 / 5000 = 0
    assert n == 0


# ── validate_position ─────────────────────────────────────────────────────────

def test_validate_passes():
    ok, msg = validate_position(50_000, 1_000, 2_500)
    assert ok
    assert "passes" in msg.lower()


def test_validate_fails_exceeds_per_trade_limit():
    ok, msg = validate_position(50_000, 3_000, 2_500)
    assert not ok
    assert "exceeds" in msg.lower()


def test_validate_fails_exceeds_5pct_cap():
    ok, msg = validate_position(50_000, 3_000, 5_000)
    assert not ok
    assert "5%" in msg or "5.0%" in msg or "cap" in msg.lower() or "exceeds" in msg.lower()


def test_validate_zero_max_loss():
    ok, _ = validate_position(50_000, 0, 2_500)
    assert ok  # No meaningful loss; pass with caution message


# ── expected_value ────────────────────────────────────────────────────────────

def test_expected_value_positive():
    ev = expected_value(0.70, 100, 50)
    # 0.70*100 - 0.30*50 = 70 - 15 = 55
    assert abs(ev - 55.0) < 1e-9


def test_expected_value_negative():
    ev = expected_value(0.30, 50, 200)
    # 0.30*50 - 0.70*200 = 15 - 140 = -125
    assert abs(ev - (-125.0)) < 1e-9


def test_expected_value_breakeven():
    ev = expected_value(0.50, 100, 100)
    assert ev == 0.0
