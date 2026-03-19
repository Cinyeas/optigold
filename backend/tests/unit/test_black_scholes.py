"""Unit tests for Black-Scholes-Merton pricing, Greeks, and IV solver."""

import math
import pytest
from app.quant.black_scholes import bs_price, bs_greeks, implied_volatility, put_call_parity_check


# ── bs_price ─────────────────────────────────────────────────────────────────

def test_atm_call_price_known_value():
    """ATM call: S=K=100, T=1, r=0.05, sigma=0.2 → ~10.45."""
    price = bs_price(S=100, K=100, T=1, r=0.05, sigma=0.2, option_type="call")
    assert abs(price - 10.45) < 0.05, f"Expected ~10.45, got {price:.4f}"


def test_atm_put_price_known_value():
    """ATM put: S=K=100, T=1, r=0.05, sigma=0.2 → ~5.57 (via put-call parity)."""
    call = bs_price(100, 100, 1, 0.05, 0.2, "call")
    put = bs_price(100, 100, 1, 0.05, 0.2, "put")
    # Put = Call - S + K*e^(-rT)
    expected_put = call - 100 + 100 * math.exp(-0.05)
    assert abs(put - expected_put) < 1e-6


def test_deep_itm_call_approaches_intrinsic():
    """Deep ITM call: S=150, K=100, T=0.01, r=0.05, sigma=0.2 → ≈ 50."""
    price = bs_price(150, 100, 0.01, 0.05, 0.2, "call")
    assert price > 49.0


def test_deep_otm_call_near_zero():
    """Deep OTM call: S=100, K=200, T=0.1, r=0.05, sigma=0.2 → near 0."""
    price = bs_price(100, 200, 0.1, 0.05, 0.2, "call")
    assert price < 0.01


def test_call_price_increases_with_sigma():
    """Vega: call price must increase with higher implied volatility."""
    p_low = bs_price(100, 100, 0.5, 0.05, 0.15, "call")
    p_high = bs_price(100, 100, 0.5, 0.05, 0.30, "call")
    assert p_high > p_low


def test_call_price_increases_with_spot():
    """Delta: call price must increase as spot price rises."""
    p_low = bs_price(95, 100, 0.5, 0.05, 0.2, "call")
    p_high = bs_price(105, 100, 0.5, 0.05, 0.2, "call")
    assert p_high > p_low


def test_put_price_decreases_with_spot():
    """Delta: put price must decrease as spot price rises."""
    p_low = bs_price(95, 100, 0.5, 0.05, 0.2, "put")
    p_high = bs_price(105, 100, 0.5, 0.05, 0.2, "put")
    assert p_high < p_low


# ── Put-call parity ───────────────────────────────────────────────────────────

def test_put_call_parity():
    """C - P = S - K*e^(-rT) must hold within 1 cent."""
    S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.2
    call = bs_price(S, K, T, r, sigma, "call")
    put = bs_price(S, K, T, r, sigma, "put")
    lhs = call - put
    rhs = S - K * math.exp(-r * T)
    assert abs(lhs - rhs) < 0.001


def test_put_call_parity_otm():
    """Parity holds for OTM options too."""
    S, K, T, r, sigma = 100, 110, 0.5, 0.03, 0.25
    call = bs_price(S, K, T, r, sigma, "call")
    put = bs_price(S, K, T, r, sigma, "put")
    rhs = S - K * math.exp(-r * T)
    assert abs((call - put) - rhs) < 0.001


# ── bs_greeks ─────────────────────────────────────────────────────────────────

def test_atm_call_delta_slightly_above_half():
    """ATM call delta should be slightly above 0.5."""
    g = bs_greeks(100, 100, 1.0, 0.05, 0.2, "call")
    assert 0.50 < g["delta"] < 0.65, f"ATM call delta = {g['delta']:.4f}"


def test_atm_put_delta_slightly_below_neg_half():
    """ATM put delta should be negative (put loses value as spot rises)."""
    g = bs_greeks(100, 100, 1.0, 0.05, 0.2, "put")
    # For ATM put with r>0 and time, delta = N(d1)-1 which is between -0.5 and -0.3
    assert -0.55 < g["delta"] < -0.30, f"ATM put delta = {g['delta']:.4f}"


def test_deep_itm_call_delta_near_one():
    """Deep ITM call delta → 1."""
    g = bs_greeks(200, 100, 1.0, 0.05, 0.2, "call")
    assert g["delta"] > 0.99


def test_deep_otm_put_delta_near_zero():
    """Deep OTM put delta → 0 (absolute value near 0)."""
    g = bs_greeks(200, 100, 1.0, 0.05, 0.2, "put")
    assert abs(g["delta"]) < 0.01


def test_call_put_delta_relationship():
    """Call delta - put delta = 1 (standard identity)."""
    S, K, T, r, sigma = 100, 105, 0.5, 0.04, 0.22
    call_g = bs_greeks(S, K, T, r, sigma, "call")
    put_g = bs_greeks(S, K, T, r, sigma, "put")
    assert abs(call_g["delta"] - put_g["delta"] - 1.0) < 1e-6


def test_gamma_is_positive():
    """Gamma must always be positive for both calls and puts."""
    for opt in ("call", "put"):
        g = bs_greeks(100, 100, 0.5, 0.05, 0.2, opt)
        assert g["gamma"] > 0, f"Gamma should be positive for {opt}"


def test_theta_is_negative_for_long():
    """Theta (from buyer's perspective) must be negative — time decay."""
    for opt in ("call", "put"):
        g = bs_greeks(100, 100, 0.5, 0.05, 0.2, opt)
        assert g["theta"] < 0, f"Theta should be negative for long {opt}"


def test_vega_is_positive():
    """Vega ($/1% IV move) must be positive."""
    for opt in ("call", "put"):
        g = bs_greeks(100, 100, 0.5, 0.05, 0.2, opt)
        assert g["vega"] > 0, f"Vega should be positive for {opt}"


def test_call_and_put_have_same_gamma_and_vega():
    """Gamma and vega are equal for same-strike call and put."""
    S, K, T, r, sigma = 100, 100, 0.5, 0.05, 0.2
    call_g = bs_greeks(S, K, T, r, sigma, "call")
    put_g = bs_greeks(S, K, T, r, sigma, "put")
    assert abs(call_g["gamma"] - put_g["gamma"]) < 1e-10
    assert abs(call_g["vega"] - put_g["vega"]) < 1e-10


# ── Implied volatility solver ─────────────────────────────────────────────────

def test_iv_round_trip_call():
    """IV solver should recover sigma=0.25 from a BS-priced call."""
    S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.25
    price = bs_price(S, K, T, r, sigma, "call")
    iv = implied_volatility(price, S, K, T, r, "call")
    assert abs(iv - sigma) < 0.0001, f"Expected IV≈0.25, got {iv:.6f}"


def test_iv_round_trip_put():
    """IV solver should recover sigma=0.30 from a BS-priced put."""
    S, K, T, r, sigma = 100, 95, 0.5, 0.04, 0.30
    price = bs_price(S, K, T, r, sigma, "put")
    iv = implied_volatility(price, S, K, T, r, "put")
    assert abs(iv - sigma) < 0.0001, f"Expected IV≈0.30, got {iv:.6f}"


def test_iv_round_trip_high_sigma():
    """IV solver handles high volatility (sigma=0.55)."""
    S, K, T, r, sigma = 100, 110, 0.75, 0.03, 0.55
    price = bs_price(S, K, T, r, sigma, "call")
    iv = implied_volatility(price, S, K, T, r, "call")
    assert abs(iv - sigma) < 0.001


def test_iv_returns_nan_for_below_intrinsic():
    """IV solver returns NaN when market price < intrinsic value."""
    # A call priced well below intrinsic
    iv = implied_volatility(0.01, S=110, K=100, T=0.5, r=0.05, option_type="call")
    assert math.isnan(iv)


# ── put_call_parity_check helper ──────────────────────────────────────────────

def test_parity_check_passes():
    S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.2
    call = bs_price(S, K, T, r, sigma, "call")
    put = bs_price(S, K, T, r, sigma, "put")
    assert put_call_parity_check(call, put, S, K, T, r)


def test_parity_check_fails_with_bad_prices():
    assert not put_call_parity_check(20.0, 1.0, S=100, K=100, T=1.0, r=0.05)
