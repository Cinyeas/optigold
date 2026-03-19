from __future__ import annotations

"""
Hard eligibility gate — applied BEFORE scoring to eliminate strategies
that must not be recommended regardless of score.

This is a hard constraint layer, not a scoring penalty.
"""

from app.quant.market_regime import MarketRegime

# In crash_risk, only protective/directional-short strategies are valid.
# All premium-selling strategies are forbidden — the environment is adverse
# for theta decay and tail risk is asymmetrically large.
_CRASH_RISK_WHITELIST: frozenset[str] = frozenset({"long_put", "bear_call_spread"})

# During high-impact events (earnings, Fed, CPI) within the DTE window,
# range-bound short-volatility strategies face Gamma blowup risk.
_EVENT_RISK_BLACKLIST: frozenset[str] = frozenset(
    {"iron_condor", "iron_butterfly", "short_straddle"}
)


def apply_eligibility_gate(
    strategies: list[str],
    regime: MarketRegime,
    upcoming_events: list[dict],
    dte: int,
) -> list[str]:
    """
    Remove strategies that are categorically unsuitable for the current
    market environment, regardless of their composite score.

    Args:
        strategies:       List of strategy names that passed suitability scoring.
        regime:           Detected MarketRegime.
        upcoming_events:  List of dicts with {days_away: int, impact: str}.
        dte:              Days-to-expiry for the current trade horizon.

    Returns:
        Filtered list — may be empty if all strategies are blocked.
    """
    # ── Rule 1: Crash regime — protect capital, never sell volatility ─────────
    if regime.regime == "crash_risk":
        strategies = [s for s in strategies if s in _CRASH_RISK_WHITELIST]

    # ── Rule 2: High-impact event inside DTE — ban Gamma-sensitive shorts ─────
    has_high_impact_event = any(
        e.get("impact") == "high" and (e.get("days_away") or 999) <= dte
        for e in upcoming_events
    )
    if has_high_impact_event:
        strategies = [s for s in strategies if s not in _EVENT_RISK_BLACKLIST]

    return strategies
