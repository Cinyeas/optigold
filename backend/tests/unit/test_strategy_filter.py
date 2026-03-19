"""Unit tests for strategy filtering."""

import pytest
from app.quant.market_regime import MarketRegime, detect_regime
from app.quant.strategy_filter import filter_strategies, StrategyCandidate
from app.quant.user_profile_matcher import UserProfile, strategy_suitability_scores


def _make_regime(regime_name: str, bias: str = "neutral") -> MarketRegime:
    return MarketRegime(
        regime=regime_name,
        bias=bias,
        confidence=0.75,
        trend_signal="flat",
        vol_signal="normal",
        momentum_signal="neutral",
        adx_signal="moderate",
    )


def _default_suitability() -> dict[str, float]:
    """Intermediate user with multi-leg enabled."""
    profile = UserProfile(
        accepts_options=True,
        accepts_multi_leg=True,
        experience_level="intermediate",
        time_horizon="monthly",
        risk_multiplier=0.5,
    )
    return strategy_suitability_scores(profile)


# ── filter_strategies ─────────────────────────────────────────────────────────

def test_returns_list_of_candidates():
    regime = _make_regime("low_vol_range")
    suit = _default_suitability()
    result = filter_strategies(regime, suit)
    assert isinstance(result, list)
    assert len(result) > 0


def test_candidates_are_sorted_by_combined_score():
    regime = _make_regime("low_vol_range")
    suit = _default_suitability()
    result = filter_strategies(regime, suit)
    scores = [c.combined_score for c in result]
    assert scores == sorted(scores, reverse=True)


def test_iron_condor_top_in_low_vol_range():
    """Iron condor should score very high in a low-vol range regime."""
    regime = _make_regime("low_vol_range")
    suit = _default_suitability()
    result = filter_strategies(regime, suit, top_n=3)
    names = [c.name for c in result]
    assert "iron_condor" in names, f"iron_condor not in top candidates: {names}"


def test_long_put_top_in_crash_risk():
    """Long put should rank highly during crash risk."""
    regime = _make_regime("crash_risk", bias="bearish")
    suit = _default_suitability()
    result = filter_strategies(regime, suit, top_n=3)
    names = [c.name for c in result]
    assert "long_put" in names or "bear_call_spread" in names, (
        f"Expected protective strategy in top 3, got: {names}"
    )


def test_beginner_no_multi_leg():
    """Beginner without multi-leg acceptance should not see iron_condor."""
    profile = UserProfile(
        accepts_options=True,
        accepts_multi_leg=False,
        experience_level="beginner",
        time_horizon="monthly",
    )
    suit = strategy_suitability_scores(profile)
    regime = _make_regime("low_vol_range")
    result = filter_strategies(regime, suit)
    names = [c.name for c in result]
    assert "iron_condor" not in names
    assert "iron_butterfly" not in names


def test_min_combined_score_filter():
    """Setting a high threshold should reduce candidates."""
    regime = _make_regime("choppy")
    suit = _default_suitability()
    strict = filter_strategies(regime, suit, min_combined_score=0.7)
    lenient = filter_strategies(regime, suit, min_combined_score=0.1)
    assert len(strict) <= len(lenient)


def test_top_n_limit():
    regime = _make_regime("low_vol_range")
    suit = _default_suitability()
    result = filter_strategies(regime, suit, top_n=2)
    assert len(result) <= 2


def test_combined_score_is_geometric_mean():
    """StrategyCandidate.combined_score = sqrt(regime_fit * suitability)."""
    import math
    c = StrategyCandidate(name="test", regime_fit=0.8, suitability=0.6)
    expected = math.sqrt(0.8 * 0.6)
    assert abs(c.combined_score - expected) < 1e-9


def test_zero_suitability_excluded():
    """Strategies with suitability=0 must be excluded from candidates."""
    regime = _make_regime("low_vol_range")
    suit = {k: 0.0 for k in ["iron_condor", "cash_secured_put"]}
    result = filter_strategies(regime, suit)
    names = [c.name for c in result]
    assert "iron_condor" not in names
    assert "cash_secured_put" not in names


def test_no_options_accepted():
    """User who doesn't accept options gets empty candidates."""
    profile = UserProfile(accepts_options=False)
    suit = strategy_suitability_scores(profile)
    regime = _make_regime("low_vol_trend_up")
    result = filter_strategies(regime, suit, min_combined_score=0.0)
    # All option strategies should have 0 suitability → no valid candidates
    assert all(c.combined_score == 0.0 for c in result)
