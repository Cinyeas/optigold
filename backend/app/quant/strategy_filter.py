from __future__ import annotations

"""Filter and rank strategies by regime × user suitability fit."""

from dataclasses import dataclass, field

from app.quant.market_regime import MarketRegime


@dataclass
class StrategyCandidate:
    """A strategy that has passed regime and suitability filters."""

    name: str
    regime_fit: float     # 0.0 – 1.0 — how well strategy suits current regime
    suitability: float    # 0.0 – 1.0 — how well strategy suits user profile
    combined_score: float = field(init=False)

    def __post_init__(self) -> None:
        # Geometric mean to require both dimensions to be decent
        self.combined_score = (self.regime_fit * self.suitability) ** 0.5


# ── Regime → strategy fit matrix ──────────────────────────────────────────────
# Values represent how well a strategy fits the regime (0 = poor, 1 = ideal)
_REGIME_STRATEGY_FIT: dict[str, dict[str, float]] = {
    "low_vol_range": {
        "iron_condor": 0.95,
        "iron_butterfly": 0.90,
        "cash_secured_put": 0.80,
        "covered_call": 0.80,
        "bull_put_spread": 0.70,
        "bear_call_spread": 0.70,
        "long_straddle": 0.10,
        "long_call": 0.30,
        "long_put": 0.30,
        "short_straddle": 0.85,
    },
    "low_vol_trend_up": {
        "cash_secured_put": 0.85,
        "covered_call": 0.75,
        "bull_put_spread": 0.90,
        "long_call": 0.80,
        "iron_condor": 0.50,
        "bear_call_spread": 0.20,
        "long_put": 0.10,
        "iron_butterfly": 0.40,
        "long_straddle": 0.25,
        "short_straddle": 0.45,
    },
    "low_vol_trend_down": {
        "long_put": 0.85,
        "bear_call_spread": 0.90,
        "long_call": 0.10,
        "cash_secured_put": 0.20,
        "covered_call": 0.20,
        "bull_put_spread": 0.20,
        "iron_condor": 0.50,
        "iron_butterfly": 0.40,
        "long_straddle": 0.25,
        "short_straddle": 0.40,
    },
    "high_vol_range": {
        "iron_condor": 0.85,
        "iron_butterfly": 0.80,
        "cash_secured_put": 0.75,
        "covered_call": 0.75,
        "bull_put_spread": 0.70,
        "bear_call_spread": 0.70,
        "long_straddle": 0.30,
        "long_call": 0.35,
        "long_put": 0.35,
        "short_straddle": 0.65,
    },
    "high_vol_trend_up": {
        "bull_put_spread": 0.85,
        "cash_secured_put": 0.80,
        "covered_call": 0.65,
        "long_call": 0.65,
        "iron_condor": 0.40,
        "bear_call_spread": 0.15,
        "long_put": 0.10,
        "iron_butterfly": 0.35,
        "long_straddle": 0.40,
        "short_straddle": 0.30,
    },
    "high_vol_trend_down": {
        "bear_call_spread": 0.85,
        "long_put": 0.75,
        "long_call": 0.10,
        "cash_secured_put": 0.25,
        "covered_call": 0.25,
        "bull_put_spread": 0.20,
        "iron_condor": 0.40,
        "iron_butterfly": 0.35,
        "long_straddle": 0.40,
        "short_straddle": 0.30,
    },
    "strong_trend_up": {
        "long_call": 0.90,
        "bull_put_spread": 0.85,
        "cash_secured_put": 0.75,
        "covered_call": 0.60,
        "bear_call_spread": 0.05,
        "long_put": 0.05,
        "iron_condor": 0.25,
        "iron_butterfly": 0.20,
        "long_straddle": 0.35,
        "short_straddle": 0.20,
    },
    "strong_trend_down": {
        "long_put": 0.90,
        "bear_call_spread": 0.85,
        "long_call": 0.05,
        "cash_secured_put": 0.15,
        "covered_call": 0.15,
        "bull_put_spread": 0.10,
        "iron_condor": 0.25,
        "iron_butterfly": 0.20,
        "long_straddle": 0.35,
        "short_straddle": 0.20,
    },
    "crash_risk": {
        "long_put": 0.90,
        "bear_call_spread": 0.75,
        "long_call": 0.05,
        "cash_secured_put": 0.05,
        "covered_call": 0.05,
        "bull_put_spread": 0.05,
        "iron_condor": 0.10,
        "iron_butterfly": 0.05,
        "long_straddle": 0.60,
        "short_straddle": 0.05,
    },
    "choppy": {
        "iron_condor": 0.75,
        "iron_butterfly": 0.70,
        "cash_secured_put": 0.60,
        "covered_call": 0.60,
        "bull_put_spread": 0.55,
        "bear_call_spread": 0.55,
        "long_straddle": 0.20,
        "long_call": 0.30,
        "long_put": 0.30,
        "short_straddle": 0.60,
    },
}


def filter_strategies(
    regime: MarketRegime,
    suitability: dict[str, float],
    min_combined_score: float = 0.30,
    top_n: int = 5,
) -> list[StrategyCandidate]:
    """
    Combine regime fit and user suitability to rank candidate strategies.

    Args:
        regime:             Detected market regime.
        suitability:        Per-strategy suitability scores from user profile matcher.
        min_combined_score: Minimum geometric mean score to include a candidate.
        top_n:              Maximum candidates to return.

    Returns:
        List of StrategyCandidate sorted by combined_score descending.
    """
    regime_fits = _REGIME_STRATEGY_FIT.get(
        regime.regime, _REGIME_STRATEGY_FIT["choppy"]
    ).copy()  # copy so we can apply dynamic adjustments without mutating the constant

    # ── ADX trend filter: penalise range-bound strategies in strong trends ──
    # Iron condors and butterflies require the underlying to stay within a range.
    # When ADX is strong (>25) with a clear directional trend, they get hit on one
    # wing. Reduce their regime_fit dynamically so directional spreads win instead.
    _RANGE_STRATEGIES = {"iron_condor", "iron_butterfly", "short_straddle"}
    if regime.adx_signal == "strong" and regime.trend_signal in ("up", "down"):
        for s in _RANGE_STRATEGIES:
            if s in regime_fits:
                regime_fits[s] = regime_fits[s] * 0.40  # cut fit by 60%

    # Moderate ADX with trend: smaller penalty
    elif regime.adx_signal == "moderate" and regime.trend_signal in ("up", "down"):
        for s in _RANGE_STRATEGIES:
            if s in regime_fits:
                regime_fits[s] = regime_fits[s] * 0.70  # cut fit by 30%

    candidates: list[StrategyCandidate] = []
    for strategy, suit_score in suitability.items():
        if suit_score <= 0:
            continue
        r_fit = regime_fits.get(strategy, 0.3)
        candidate = StrategyCandidate(
            name=strategy,
            regime_fit=r_fit,
            suitability=suit_score,
        )
        if candidate.combined_score >= min_combined_score:
            candidates.append(candidate)

    candidates.sort(key=lambda c: c.combined_score, reverse=True)
    return candidates[:top_n]
