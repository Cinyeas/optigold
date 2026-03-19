from __future__ import annotations

"""Generate concrete option parameters for a chosen strategy."""

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from app.quant.black_scholes import bs_price, bs_greeks


@dataclass
class StrategyParameters:
    """Concrete parameters for a tradeable option position."""

    strategy: str
    instrument: str = "GLD"
    strike_a: Optional[float] = None
    strike_b: Optional[float] = None
    expiry: Optional[date] = None
    dte: int = 0              # days to expiry
    quantity: int = 1
    premium_collected: float = 0.0  # positive = credit
    premium_paid: float = 0.0       # positive = debit
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven_a: Optional[float] = None
    breakeven_b: Optional[float] = None
    probability_of_profit: float = 0.0
    greeks: dict = field(default_factory=dict)
    option_type_a: str = "put"      # leg-A option type
    option_type_b: str = "call"     # leg-B option type (where applicable)


def _next_expiry(dte_target: int = 30) -> date:
    """Return the nearest Friday >= today + dte_target days."""
    target = date.today() + timedelta(days=dte_target)
    days_until_friday = (4 - target.weekday()) % 7
    return target + timedelta(days=days_until_friday)


def _round_strike(price: float, increment: float = 1.0) -> float:
    """Round to nearest strike increment."""
    return round(price / increment) * increment


def _time_to_expiry(expiry: date) -> float:
    """Years from today to expiry (minimum 1 day)."""
    days = (expiry - date.today()).days
    return max(days, 1) / 365.0


def generate_parameters(
    strategy: str,
    spot: float,
    atm_iv: float,
    r: float = 0.05,
    dte_target: int = 30,
    quantity: int = 1,
    delta_target_otm: float = 0.30,
) -> StrategyParameters:
    """
    Build StrategyParameters using synthetic Black-Scholes chain.

    Args:
        strategy:         Strategy name from filter (e.g. "iron_condor").
        spot:             Current GLD spot price.
        atm_iv:           ATM implied volatility (decimal, e.g. 0.18).
        r:                Risk-free rate.
        dte_target:       Target days to expiry.
        quantity:         Number of contracts.
        delta_target_otm: Target delta magnitude for OTM short strikes.

    Returns:
        StrategyParameters with all concrete fields populated.
    """
    expiry = _next_expiry(dte_target)
    T = _time_to_expiry(expiry)
    dte = (expiry - date.today()).days

    # Use a slightly elevated IV for OTM strikes (simplified skew)
    iv_otm = atm_iv * 1.05

    params = StrategyParameters(
        strategy=strategy,
        instrument="GLD",
        expiry=expiry,
        dte=dte,
        quantity=quantity,
    )

    if strategy == "cash_secured_put":
        # Short OTM put at ~30-delta
        strike = _find_strike_by_delta(spot, T, r, iv_otm, delta_target_otm, "put")
        premium = bs_price(spot, strike, T, r, iv_otm, "put") * 100 * quantity
        greeks = bs_greeks(spot, strike, T, r, iv_otm, "put")

        params.strike_a = strike
        params.option_type_a = "put"
        params.premium_collected = round(premium, 2)
        params.max_profit = round(premium, 2)
        params.max_loss = round((strike * 100 * quantity) - premium, 2)
        params.breakeven_a = round(strike - premium / (100 * quantity), 2)
        params.probability_of_profit = round((1 - delta_target_otm) * 100, 1)
        params.greeks = greeks

    elif strategy == "covered_call":
        # Short OTM call at ~30-delta
        strike = _find_strike_by_delta(spot, T, r, iv_otm, delta_target_otm, "call")
        premium = bs_price(spot, strike, T, r, iv_otm, "call") * 100 * quantity
        greeks = bs_greeks(spot, strike, T, r, iv_otm, "call")

        params.strike_a = strike
        params.option_type_a = "call"
        params.premium_collected = round(premium, 2)
        params.max_profit = round(premium + (strike - spot) * 100 * quantity, 2)
        params.max_loss = round((spot * 100 * quantity) - premium, 2)
        params.breakeven_a = round(spot - premium / (100 * quantity), 2)
        params.probability_of_profit = round((1 - delta_target_otm) * 100, 1)
        params.greeks = greeks

    elif strategy == "bull_put_spread":
        short_strike = _find_strike_by_delta(spot, T, r, iv_otm, delta_target_otm, "put")
        long_strike = _round_strike(short_strike - max(2.0, spot * 0.02))
        short_prem = bs_price(spot, short_strike, T, r, iv_otm, "put")
        long_prem = bs_price(spot, long_strike, T, r, iv_otm, "put")
        net_credit = (short_prem - long_prem) * 100 * quantity
        width = (short_strike - long_strike) * 100 * quantity

        params.strike_a = long_strike
        params.strike_b = short_strike
        params.option_type_a = "put"
        params.premium_collected = round(net_credit, 2)
        params.max_profit = round(net_credit, 2)
        params.max_loss = round(width - net_credit, 2)
        params.breakeven_a = round(short_strike - net_credit / (100 * quantity), 2)
        params.probability_of_profit = round((1 - delta_target_otm) * 100, 1)
        params.greeks = bs_greeks(spot, short_strike, T, r, iv_otm, "put")

    elif strategy == "bear_call_spread":
        short_strike = _find_strike_by_delta(spot, T, r, iv_otm, delta_target_otm, "call")
        long_strike = _round_strike(short_strike + max(2.0, spot * 0.02))
        short_prem = bs_price(spot, short_strike, T, r, iv_otm, "call")
        long_prem = bs_price(spot, long_strike, T, r, iv_otm, "call")
        net_credit = (short_prem - long_prem) * 100 * quantity
        width = (long_strike - short_strike) * 100 * quantity

        params.strike_a = short_strike
        params.strike_b = long_strike
        params.option_type_a = "call"
        params.premium_collected = round(net_credit, 2)
        params.max_profit = round(net_credit, 2)
        params.max_loss = round(width - net_credit, 2)
        params.breakeven_a = round(short_strike + net_credit / (100 * quantity), 2)
        params.probability_of_profit = round((1 - delta_target_otm) * 100, 1)
        params.greeks = bs_greeks(spot, short_strike, T, r, iv_otm, "call")

    elif strategy == "iron_condor":
        short_put = _find_strike_by_delta(spot, T, r, iv_otm, delta_target_otm, "put")
        long_put = _round_strike(short_put - max(2.0, spot * 0.02))
        short_call = _find_strike_by_delta(spot, T, r, iv_otm, delta_target_otm, "call")
        long_call = _round_strike(short_call + max(2.0, spot * 0.02))

        sp_prem = bs_price(spot, short_put, T, r, iv_otm, "put")
        lp_prem = bs_price(spot, long_put, T, r, iv_otm, "put")
        sc_prem = bs_price(spot, short_call, T, r, iv_otm, "call")
        lc_prem = bs_price(spot, long_call, T, r, iv_otm, "call")
        net_credit = (sp_prem - lp_prem + sc_prem - lc_prem) * 100 * quantity
        put_width = (short_put - long_put) * 100 * quantity

        params.strike_a = short_put
        params.strike_b = short_call
        params.option_type_a = "put"
        params.option_type_b = "call"
        params.premium_collected = round(net_credit, 2)
        params.max_profit = round(net_credit, 2)
        params.max_loss = round(put_width - net_credit, 2)
        params.breakeven_a = round(short_put - net_credit / (100 * quantity), 2)
        params.breakeven_b = round(short_call + net_credit / (100 * quantity), 2)
        params.probability_of_profit = round((1 - 2 * delta_target_otm) * 100, 1)
        params.greeks = bs_greeks(spot, short_put, T, r, iv_otm, "put")

    elif strategy == "iron_butterfly":
        atm_strike = _round_strike(spot)
        wing = max(3.0, spot * 0.015)
        long_put = _round_strike(atm_strike - wing)
        long_call = _round_strike(atm_strike + wing)
        sp_prem = bs_price(spot, atm_strike, T, r, atm_iv, "put")
        sc_prem = bs_price(spot, atm_strike, T, r, atm_iv, "call")
        lp_prem = bs_price(spot, long_put, T, r, iv_otm, "put")
        lc_prem = bs_price(spot, long_call, T, r, iv_otm, "call")
        net_credit = (sp_prem + sc_prem - lp_prem - lc_prem) * 100 * quantity
        width = wing * 100 * quantity

        params.strike_a = atm_strike
        params.strike_b = atm_strike
        params.premium_collected = round(net_credit, 2)
        params.max_profit = round(net_credit, 2)
        params.max_loss = round(width - net_credit, 2)
        params.breakeven_a = round(atm_strike - net_credit / (100 * quantity), 2)
        params.breakeven_b = round(atm_strike + net_credit / (100 * quantity), 2)
        params.probability_of_profit = 40.0
        params.greeks = bs_greeks(spot, atm_strike, T, r, atm_iv, "put")

    elif strategy == "long_call":
        strike = _round_strike(spot * 1.01)  # slight OTM
        premium = bs_price(spot, strike, T, r, atm_iv, "call") * 100 * quantity
        params.strike_a = strike
        params.option_type_a = "call"
        params.premium_paid = round(premium, 2)
        params.max_loss = round(premium, 2)
        params.max_profit = round(spot * 3 * 100 * quantity, 2)  # theoretical cap: 3× spot
        params.breakeven_a = round(strike + premium / (100 * quantity), 2)
        params.probability_of_profit = round(delta_target_otm * 100, 1)
        params.greeks = bs_greeks(spot, strike, T, r, atm_iv, "call")

    elif strategy == "long_put":
        strike = _round_strike(spot * 0.99)  # slight OTM
        premium = bs_price(spot, strike, T, r, atm_iv, "put") * 100 * quantity
        params.strike_a = strike
        params.option_type_a = "put"
        params.premium_paid = round(premium, 2)
        params.max_loss = round(premium, 2)
        params.max_profit = round(strike * 100 * quantity - premium, 2)
        params.breakeven_a = round(strike - premium / (100 * quantity), 2)
        params.probability_of_profit = round(delta_target_otm * 100, 1)
        params.greeks = bs_greeks(spot, strike, T, r, atm_iv, "put")

    elif strategy == "long_straddle":
        strike = _round_strike(spot)
        call_prem = bs_price(spot, strike, T, r, atm_iv, "call")
        put_prem = bs_price(spot, strike, T, r, atm_iv, "put")
        total_prem = (call_prem + put_prem) * 100 * quantity
        params.strike_a = strike
        params.premium_paid = round(total_prem, 2)
        params.max_loss = round(total_prem, 2)
        params.max_profit = round(spot * 3 * 100 * quantity, 2)  # theoretical cap: 3× spot
        params.breakeven_a = round(strike - total_prem / (100 * quantity), 2)
        params.breakeven_b = round(strike + total_prem / (100 * quantity), 2)
        params.probability_of_profit = 40.0
        params.greeks = {
            k: bs_greeks(spot, strike, T, r, atm_iv, "call")[k]
            + bs_greeks(spot, strike, T, r, atm_iv, "put")[k]
            for k in ("delta", "gamma", "theta", "vega", "rho")
        }

    else:
        # Fallback: treat as cash-secured put
        return generate_parameters(
            "cash_secured_put", spot, atm_iv, r, dte_target, quantity, delta_target_otm
        )

    return params


def _find_strike_by_delta(
    spot: float,
    T: float,
    r: float,
    sigma: float,
    target_delta: float,
    option_type: str,
    increment: float = 1.0,
    search_range: int = 80,
) -> float:
    """
    Binary-search-like scan to find the strike whose |delta| is closest
    to *target_delta*.

    Returns the nearest strike.
    """
    from app.quant.black_scholes import bs_greeks as _bsg

    best_strike = _round_strike(spot)
    best_diff = float("inf")

    low = _round_strike(spot * 0.70, increment)
    high = _round_strike(spot * 1.30, increment)
    step = increment

    k = low
    while k <= high:
        g = _bsg(spot, k, T, r, sigma, option_type)
        delta = abs(g["delta"])
        diff = abs(delta - target_delta)
        if diff < best_diff:
            best_diff = diff
            best_strike = k
        k = round(k + step, 6)

    return best_strike
