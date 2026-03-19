from __future__ import annotations

"""Multi-dimensional strategy scoring engine."""

from dataclasses import dataclass, field
from typing import Any

from app.quant.market_regime import MarketRegime
from app.quant.parameter_engine import StrategyParameters
from app.quant.strategy_filter import StrategyCandidate


@dataclass
class StrategyScore:
    """10-dimension score for a single strategy candidate."""

    strategy: str
    composite: float           # weighted average, 0–100

    # Individual dimension scores (0–100)
    regime_alignment: float = 0.0
    iv_environment: float = 0.0
    probability_of_profit: float = 0.0
    risk_reward: float = 0.0
    kelly_fraction: float = 0.0
    greeks_quality: float = 0.0
    event_risk: float = 0.0
    liquidity_proxy: float = 0.0
    time_decay_favorability: float = 0.0
    user_suitability: float = 0.0

    breakdown: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.breakdown = {
            "regime_alignment": self.regime_alignment,
            "iv_environment": self.iv_environment,
            "probability_of_profit": self.probability_of_profit,
            "risk_reward": self.risk_reward,
            "kelly_fraction": self.kelly_fraction,
            "greeks_quality": self.greeks_quality,
            "event_risk": self.event_risk,
            "liquidity_proxy": self.liquidity_proxy,
            "time_decay_favorability": self.time_decay_favorability,
            "user_suitability": self.user_suitability,
        }


# Dimension weights (must sum to 1.0)
_WEIGHTS: dict[str, float] = {
    "regime_alignment": 0.20,
    "iv_environment": 0.15,
    "probability_of_profit": 0.15,
    "risk_reward": 0.12,
    "kelly_fraction": 0.08,
    "greeks_quality": 0.08,
    "event_risk": 0.07,
    "liquidity_proxy": 0.05,
    "time_decay_favorability": 0.05,
    "user_suitability": 0.05,
}

assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


def _score_regime_alignment(candidate: StrategyCandidate, regime: MarketRegime) -> float:
    """Score how aligned the strategy is with the detected regime."""
    base = candidate.regime_fit * 100
    # Boost if regime confidence is high
    bonus = regime.confidence * 10
    return min(100.0, base + bonus)


def _score_iv_environment(strategy: str, iv_rank: float) -> float:
    """
    IV-environment favourability.

    Premium sellers benefit from high IV; buyers from low IV.
    Thresholds based on OptionAlpha/QuantConnect research:
      - Sellers: IV Rank ≥ 50 ideal; < 30 = poor risk/reward (premium too cheap)
      - Buyers:  IV Rank < 30 ideal; ≥ 70 = avoid (IV crush risk after entry)
    """
    premium_sellers = {
        "cash_secured_put", "covered_call", "bull_put_spread",
        "bear_call_spread", "iron_condor", "iron_butterfly", "short_straddle",
    }
    if strategy in premium_sellers:
        if iv_rank >= 70:
            return 100.0                          # optimal — sell expensive premium
        if iv_rank >= 50:
            return 80.0 + (iv_rank - 50) * 1.0   # good zone
        if iv_rank >= 30:
            return 40.0 + (iv_rank - 30) * 2.0   # marginal — premium thin
        # IV Rank < 30: premium too cheap, penalise heavily
        return max(0.0, iv_rank * 0.8)
    else:
        # Buyers prefer low IV (cheap premium, no IV crush on entry)
        if iv_rank <= 20:
            return 100.0
        if iv_rank <= 40:
            return 100.0 - (iv_rank - 20) * 2.0
        return min(100.0, max(0.0, (100 - iv_rank) * 1.2))


def _score_probability_of_profit(pop: float) -> float:
    """Convert POP% to a score.  Penalise very low and very high POP."""
    # Sweet spot: 65–85%
    if 65 <= pop <= 85:
        return 90.0
    if 55 <= pop < 65:
        return 75.0
    if 85 < pop <= 95:
        return 70.0
    if pop > 95:
        return 55.0   # too wide/safe → little edge
    return max(0.0, pop)  # <55%


def _score_risk_reward(max_profit: float, max_loss: float) -> float:
    """
    Score based on max-profit / max-loss ratio.

    For credit spreads a 1:3 risk/reward (profit = 0.33 * loss) is acceptable.
    For debit spreads we want profit >= loss.
    """
    if max_loss <= 0:
        return 50.0
    if max_profit == float("inf"):
        return 80.0  # unlimited upside; moderate score (theta risk)
    ratio = max_profit / max_loss
    if ratio >= 1.0:
        return 95.0
    if ratio >= 0.5:
        return 80.0
    if ratio >= 0.33:
        return 65.0
    if ratio >= 0.20:
        return 50.0
    return 30.0


def _score_kelly(kelly_frac: float) -> float:
    """Higher Kelly → higher score, capped."""
    return min(100.0, kelly_frac * 400)  # 0.25 Kelly → 100


def _score_greeks(greeks: dict[str, float], strategy: str) -> float:
    """
    Quality of Greek exposure for the strategy type.

    - Premium sellers want negative theta (positive for us as short), low delta.
    - Buyers want positive delta/gamma alignment.
    """
    theta = greeks.get("theta", 0.0)
    delta = greeks.get("delta", 0.0)
    vega = greeks.get("vega", 0.0)

    premium_sellers = {
        "cash_secured_put", "covered_call", "bull_put_spread",
        "bear_call_spread", "iron_condor", "iron_butterfly", "short_straddle",
    }
    if strategy in premium_sellers:
        # We are short, so our P&L theta = +|theta|
        theta_score = min(100.0, abs(theta) * 365 * 2)  # normalise
        delta_score = max(0.0, 100 - abs(delta) * 200)  # prefer low delta
        return (theta_score + delta_score) / 2
    else:
        # Long directional: want delta in the right direction
        delta_score = min(100.0, abs(delta) * 200)
        return delta_score


def _score_event_risk(days_to_expiry: int, upcoming_events: list[dict]) -> float:
    """
    Penalise if a major scheduled event falls within the holding period.
    """
    base = 80.0
    for event in upcoming_events:
        days_away = event.get("days_away", 999)
        impact = event.get("impact", "low")
        if days_away <= days_to_expiry:
            if impact == "high":
                base -= 25
            elif impact == "medium":
                base -= 10
            else:
                base -= 3
    return max(0.0, base)


def _score_liquidity(strategy: str, iv_rank: float) -> float:
    """
    Proxy liquidity score for GLD options.

    GLD is highly liquid; multi-leg strategies have slightly wider spreads.
    """
    multi_leg = {"iron_condor", "iron_butterfly", "long_straddle", "short_straddle",
                 "bull_put_spread", "bear_call_spread"}
    base = 85.0 if strategy not in multi_leg else 75.0
    # Higher IV → more activity in options market
    base += iv_rank * 0.1
    return min(100.0, base)


def _score_time_decay(strategy: str, dte: int) -> float:
    """
    Theta-decay favourability.  Premium sellers want 20–45 DTE sweet spot.
    """
    premium_sellers = {
        "cash_secured_put", "covered_call", "bull_put_spread",
        "bear_call_spread", "iron_condor", "iron_butterfly", "short_straddle",
    }
    if strategy in premium_sellers:
        if 21 <= dte <= 45:
            return 90.0
        if 14 <= dte < 21:
            return 75.0
        if 45 < dte <= 60:
            return 70.0
        return 50.0
    else:
        if 14 <= dte <= 30:
            return 80.0
        return 60.0


def score_strategy(
    candidate: StrategyCandidate,
    params: StrategyParameters,
    regime: MarketRegime,
    iv_rank: float,
    kelly_frac: float,
    upcoming_events: list[dict] | None = None,
) -> StrategyScore:
    """
    Compute a StrategyScore for a candidate using all 10 dimensions.

    Args:
        candidate:       StrategyCandidate with regime_fit and suitability.
        params:          Concrete option parameters from parameter_engine.
        regime:          Detected market regime.
        iv_rank:         Current IV rank (0–100).
        kelly_frac:      Adjusted Kelly fraction for this trade.
        upcoming_events: List of dicts with keys {days_away, impact}.

    Returns:
        StrategyScore with composite and per-dimension scores.
    """
    if upcoming_events is None:
        upcoming_events = []

    d = {
        "regime_alignment": _score_regime_alignment(candidate, regime),
        "iv_environment": _score_iv_environment(candidate.name, iv_rank),
        "probability_of_profit": _score_probability_of_profit(
            params.probability_of_profit
        ),
        "risk_reward": _score_risk_reward(params.max_profit, params.max_loss),
        "kelly_fraction": _score_kelly(kelly_frac),
        "greeks_quality": _score_greeks(params.greeks, candidate.name),
        "event_risk": _score_event_risk(params.dte, upcoming_events),
        "liquidity_proxy": _score_liquidity(candidate.name, iv_rank),
        "time_decay_favorability": _score_time_decay(candidate.name, params.dte),
        "user_suitability": candidate.suitability * 100,
    }

    composite = sum(_WEIGHTS[k] * v for k, v in d.items())

    # IV Rank composite multiplier — research-backed gate:
    # Selling premium in low-IV environment has poor risk/reward regardless of other scores.
    # OptionAlpha: selling at IVR>50 improves win rate by ~9pp vs no filter.
    _PREMIUM_SELLERS = {
        "cash_secured_put", "covered_call", "bull_put_spread",
        "bear_call_spread", "iron_condor", "iron_butterfly", "short_straddle",
    }
    if candidate.name in _PREMIUM_SELLERS:
        if iv_rank < 30:
            composite *= 0.55   # heavily penalise — premium too cheap
        elif iv_rank >= 70:
            composite *= 1.15   # reward optimal selling environment (cap at 100 below)
    else:
        # Buyers benefit from low IV
        if iv_rank > 70:
            composite *= 0.80   # IV crush risk — discount directional buyers

    composite = min(100.0, round(composite, 2))

    return StrategyScore(
        strategy=candidate.name,
        composite=composite,
        **d,  # type: ignore[arg-type]
    )


def rank_strategies(scores: list[StrategyScore]) -> list[StrategyScore]:
    """Return scores sorted by composite descending."""
    return sorted(scores, key=lambda s: s.composite, reverse=True)
