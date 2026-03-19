from __future__ import annotations

"""Match user risk profile to option strategy suitability scores."""

from dataclasses import dataclass


@dataclass
class UserProfile:
    """Simplified user risk profile for strategy matching."""

    capital: float = 50_000.0
    max_loss_per_trade: float = 2_500.0
    accepts_options: bool = True
    accepts_margin: bool = False
    accepts_unlimited_risk: bool = False
    accepts_multi_leg: bool = False
    time_horizon: str = "monthly"   # "weekly", "monthly", "quarterly"
    experience_level: str = "beginner"  # "beginner", "intermediate", "advanced"
    risk_multiplier: float = 0.5


# Strategy catalogue – each strategy tagged with requirements
_STRATEGY_REQUIREMENTS: dict[str, dict] = {
    "cash_secured_put": {
        "needs_options": True,
        "needs_margin": False,
        "needs_unlimited_risk": False,
        "needs_multi_leg": False,
        "min_experience": "beginner",
        "time_horizons": {"weekly", "monthly", "quarterly"},
    },
    "covered_call": {
        "needs_options": True,
        "needs_margin": False,
        "needs_unlimited_risk": False,
        "needs_multi_leg": False,
        "min_experience": "beginner",
        "time_horizons": {"weekly", "monthly", "quarterly"},
    },
    "bull_put_spread": {
        "needs_options": True,
        "needs_margin": False,
        "needs_unlimited_risk": False,
        "needs_multi_leg": True,
        "min_experience": "intermediate",
        "time_horizons": {"weekly", "monthly"},
    },
    "bear_call_spread": {
        "needs_options": True,
        "needs_margin": False,
        "needs_unlimited_risk": False,
        "needs_multi_leg": True,
        "min_experience": "intermediate",
        "time_horizons": {"weekly", "monthly"},
    },
    "iron_condor": {
        "needs_options": True,
        "needs_margin": False,
        "needs_unlimited_risk": False,
        "needs_multi_leg": True,
        "min_experience": "intermediate",
        "time_horizons": {"monthly", "quarterly"},
    },
    "iron_butterfly": {
        "needs_options": True,
        "needs_margin": False,
        "needs_unlimited_risk": False,
        "needs_multi_leg": True,
        "min_experience": "advanced",
        "time_horizons": {"monthly"},
    },
    "long_call": {
        "needs_options": True,
        "needs_margin": False,
        "needs_unlimited_risk": False,
        "needs_multi_leg": False,
        "min_experience": "beginner",
        "time_horizons": {"weekly", "monthly", "quarterly"},
    },
    "long_put": {
        "needs_options": True,
        "needs_margin": False,
        "needs_unlimited_risk": False,
        "needs_multi_leg": False,
        "min_experience": "beginner",
        "time_horizons": {"weekly", "monthly", "quarterly"},
    },
    "long_straddle": {
        "needs_options": True,
        "needs_margin": False,
        "needs_unlimited_risk": False,
        "needs_multi_leg": True,
        "min_experience": "intermediate",
        "time_horizons": {"weekly", "monthly"},
    },
    "short_straddle": {
        "needs_options": True,
        "needs_margin": True,
        "needs_unlimited_risk": True,
        "needs_multi_leg": True,
        "min_experience": "advanced",
        "time_horizons": {"monthly"},
    },
}

_EXPERIENCE_RANK = {"beginner": 0, "intermediate": 1, "advanced": 2}


def _meets_requirements(profile: UserProfile, req: dict) -> bool:
    """Return True if the user profile satisfies a strategy's requirements."""
    if req["needs_options"] and not profile.accepts_options:
        return False
    if req["needs_margin"] and not profile.accepts_margin:
        return False
    if req["needs_unlimited_risk"] and not profile.accepts_unlimited_risk:
        return False
    if req["needs_multi_leg"] and not profile.accepts_multi_leg:
        return False
    if profile.time_horizon not in req["time_horizons"]:
        return False
    user_rank = _EXPERIENCE_RANK.get(profile.experience_level, 0)
    min_rank = _EXPERIENCE_RANK.get(req["min_experience"], 0)
    if user_rank < min_rank:
        return False
    return True


def strategy_suitability_scores(profile: UserProfile) -> dict[str, float]:
    """
    Return a suitability score (0.0 – 1.0) for each known strategy.

    Score reflects:
    - Hard eligibility (0.0 if any requirement fails)
    - Soft bonus for experience level alignment
    - Small bonus for matching preferred time horizon
    - Risk-multiplier scaling for premium-selling strategies

    Returns:
        {strategy_name: score}
    """
    scores: dict[str, float] = {}

    for name, req in _STRATEGY_REQUIREMENTS.items():
        if not _meets_requirements(profile, req):
            scores[name] = 0.0
            continue

        base = 0.6  # eligible by default

        # Experience bonus: advanced users get a bump on complex strategies
        user_rank = _EXPERIENCE_RANK.get(profile.experience_level, 0)
        min_rank = _EXPERIENCE_RANK.get(req["min_experience"], 0)
        experience_gap = user_rank - min_rank  # 0 means exactly met, >0 means overqualified
        base += min(experience_gap * 0.05, 0.15)

        # Premium-selling strategies benefit from high risk multiplier
        premium_sellers = {
            "cash_secured_put",
            "covered_call",
            "bull_put_spread",
            "bear_call_spread",
            "iron_condor",
            "iron_butterfly",
        }
        if name in premium_sellers:
            base += profile.risk_multiplier * 0.2  # max +0.2 at full Kelly

        # Directional buyers penalised slightly for beginners (theta decay risk)
        if name in ("long_call", "long_put", "long_straddle") and profile.experience_level == "beginner":
            base -= 0.05

        scores[name] = float(min(1.0, max(0.0, base)))

    return scores
