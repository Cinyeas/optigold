from __future__ import annotations

"""Kelly Criterion position sizing utilities."""

import math


def kelly_fraction(win_prob: float, avg_win: float, avg_loss: float) -> float:
    """
    Full Kelly fraction for a binary outcome bet.

    Formula: f* = (b*p - q) / b
        where b = avg_win / avg_loss, p = win_prob, q = 1 - p.

    Args:
        win_prob:  Probability of winning (0 < p < 1).
        avg_win:   Average gain per winning trade (positive dollar amount).
        avg_loss:  Average loss per losing trade (positive dollar amount).

    Returns:
        Kelly fraction in [0, 1].  Clamped to 0 if edge is negative.
    """
    if avg_loss <= 0 or avg_win <= 0:
        return 0.0
    win_prob = max(0.0, min(1.0, win_prob))
    b = avg_win / avg_loss
    q = 1.0 - win_prob
    f = (b * win_prob - q) / b
    return float(max(0.0, min(1.0, f)))


def adjusted_kelly(fraction: float, risk_multiplier: float = 0.5) -> float:
    """
    Scale Kelly fraction by a user-defined risk multiplier.

    Hard cap: never exceed 25% of capital on a single position.

    Args:
        fraction:        Raw Kelly fraction from :func:`kelly_fraction`.
        risk_multiplier: User preference multiplier (e.g. 0.5 = half-Kelly).

    Returns:
        Adjusted Kelly fraction capped at 0.25.
    """
    adjusted = fraction * risk_multiplier
    return float(min(adjusted, 0.25))


def position_size(
    capital: float,
    max_risk_fraction: float,
    risk_per_unit: float,
) -> int:
    """
    Calculate integer number of contracts/units to trade.

    Capital allocation is capped at 5% of portfolio regardless of Kelly.

    Args:
        capital:          Total account equity in dollars.
        max_risk_fraction: Adjusted Kelly fraction (from :func:`adjusted_kelly`).
        risk_per_unit:    Maximum dollar risk per single contract/unit.

    Returns:
        Number of contracts (at least 1 if trade is viable, else 0).
    """
    if capital <= 0 or risk_per_unit <= 0:
        return 0

    # Hard 5% capital-at-risk ceiling
    max_risk_dollars = min(capital * max_risk_fraction, capital * 0.05)

    contracts = int(max_risk_dollars / risk_per_unit)
    return max(0, contracts)


def validate_position(
    capital: float,
    max_loss_total: float,
    max_loss_per_trade: float,
) -> tuple[bool, str]:
    """
    Validate whether a proposed trade respects risk guardrails.

    Args:
        capital:            Total account equity.
        max_loss_total:     Maximum possible loss for the proposed position.
        max_loss_per_trade: User's per-trade loss limit from UserProfile.

    Returns:
        (is_valid, reason_message)
    """
    if max_loss_total <= 0:
        return True, "No meaningful max-loss calculated; proceed with caution."

    if max_loss_total > max_loss_per_trade:
        return (
            False,
            f"Max loss ${max_loss_total:.0f} exceeds per-trade limit ${max_loss_per_trade:.0f}.",
        )

    pct_of_capital = max_loss_total / capital * 100.0
    if pct_of_capital > 5.0:
        return (
            False,
            f"Max loss is {pct_of_capital:.1f}% of capital — exceeds 5% hard cap.",
        )

    return True, "Position size passes all risk checks."


def expected_value(
    win_prob: float, avg_win: float, avg_loss: float
) -> float:
    """Compute simple expected value of a trade in dollars."""
    return win_prob * avg_win - (1.0 - win_prob) * avg_loss
