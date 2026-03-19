from __future__ import annotations

"""Black-Scholes-Merton option pricing, Greeks, and IV solver."""

import math
from typing import Literal

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

OptionType = Literal["call", "put"]

# Minimum time-to-expiry in years to avoid division by zero
_MIN_T = 1e-6
_MIN_SIGMA = 1e-6


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> tuple[float, float]:
    """Compute d1 and d2 for BSM formula."""
    T = max(T, _MIN_T)
    sigma = max(sigma, _MIN_SIGMA)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2


def bs_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType = "call",
) -> float:
    """
    Black-Scholes-Merton option price.

    Args:
        S: Spot price of the underlying
        K: Strike price
        T: Time to expiry in years
        r: Risk-free interest rate (annualised, decimal)
        sigma: Implied volatility (annualised, decimal)
        option_type: "call" or "put"

    Returns:
        Option fair value in dollars
    """
    T = max(T, _MIN_T)
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    discount = math.exp(-r * T)

    if option_type == "call":
        return S * norm.cdf(d1) - K * discount * norm.cdf(d2)
    else:
        return K * discount * norm.cdf(-d2) - S * norm.cdf(-d1)


def bs_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType = "call",
) -> dict[str, float]:
    """
    Compute first-order BSM Greeks.

    Returns:
        dict with:
            delta  – rate of change of price w.r.t. S
            gamma  – rate of change of delta w.r.t. S
            theta  – time decay in $/day (negative for long options)
            vega   – price change per 1% change in IV ($/1%)
            rho    – price change per 1% change in r ($/1%)
    """
    T = max(T, _MIN_T)
    sigma = max(sigma, _MIN_SIGMA)
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    discount = math.exp(-r * T)
    sqrt_T = math.sqrt(T)
    pdf_d1 = norm.pdf(d1)

    # Gamma (same for calls and puts)
    gamma = pdf_d1 / (S * sigma * sqrt_T)

    # Vega (same for calls and puts) – expressed as $/1% move in IV
    vega = S * pdf_d1 * sqrt_T * 0.01

    if option_type == "call":
        delta = norm.cdf(d1)
        theta = (
            -(S * pdf_d1 * sigma) / (2 * sqrt_T)
            - r * K * discount * norm.cdf(d2)
        ) / 365.0
        rho = K * T * discount * norm.cdf(d2) * 0.01
    else:
        delta = norm.cdf(d1) - 1.0
        theta = (
            -(S * pdf_d1 * sigma) / (2 * sqrt_T)
            + r * K * discount * norm.cdf(-d2)
        ) / 365.0
        rho = -K * T * discount * norm.cdf(-d2) * 0.01

    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "rho": rho,
    }


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: OptionType = "call",
    tol: float = 1e-6,
) -> float:
    """
    Recover implied volatility from a market option price via Brent's method.

    Returns:
        IV as a decimal (e.g. 0.25 for 25%).  Returns float('nan') if solver
        fails to converge or inputs are intrinsically invalid.
    """
    T = max(T, _MIN_T)

    # Intrinsic value bounds check
    if option_type == "call":
        intrinsic = max(S - K * math.exp(-r * T), 0.0)
    else:
        intrinsic = max(K * math.exp(-r * T) - S, 0.0)

    if market_price < intrinsic - tol:
        return float("nan")

    def objective(sigma: float) -> float:
        return bs_price(S, K, T, r, sigma, option_type) - market_price

    try:
        iv = brentq(objective, 1e-4, 10.0, xtol=tol, maxiter=500)
        return float(iv)
    except (ValueError, RuntimeError):
        return float("nan")


def put_call_parity_check(
    call_price: float,
    put_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    tol: float = 0.05,
) -> bool:
    """Return True if C - P ≈ S - K*e^(-rT) within *tol* dollars."""
    lhs = call_price - put_price
    rhs = S - K * math.exp(-r * T)
    return abs(lhs - rhs) <= tol
