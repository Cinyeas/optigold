"""Unit tests for the multi-dimensional scoring engine."""

import pytest
from app.quant.scoring_engine import (
    score_strategy,
    rank_strategies,
    StrategyScore,
    _score_regime_alignment,
    _score_iv_environment,
    _score_probability_of_profit,
    _score_risk_reward,
    _score_kelly,
    _score_event_risk,
    _score_time_decay,
)
from app.quant.market_regime import MarketRegime
from app.quant.parameter_engine import StrategyParameters
from app.quant.strategy_filter import StrategyCandidate
from datetime import date


def _make_regime(regime: str = "low_vol_range", confidence: float = 0.8) -> MarketRegime:
    return MarketRegime(
        regime=regime, bias="neutral", confidence=confidence,
        trend_signal="flat", vol_signal="low",
        momentum_signal="neutral", adx_signal="moderate",
    )


def _make_candidate(name: str = "iron_condor", regime_fit: float = 0.9, suit: float = 0.8) -> StrategyCandidate:
    return StrategyCandidate(name=name, regime_fit=regime_fit, suitability=suit)


def _make_params(
    strategy: str = "iron_condor",
    max_profit: float = 300.0,
    max_loss: float = 700.0,
    pop: float = 72.0,
    dte: int = 30,
    strike_a: float = 210.0,
    strike_b: float = 230.0,
) -> StrategyParameters:
    p = StrategyParameters(strategy=strategy)
    p.strike_a = strike_a
    p.strike_b = strike_b
    p.max_profit = max_profit
    p.max_loss = max_loss
    p.probability_of_profit = pop
    p.dte = dte
    p.expiry = date.today()
    p.greeks = {"delta": 0.15, "gamma": 0.02, "theta": -0.05, "vega": 0.10, "rho": 0.01}
    return p


# ── Individual dimension scorers ──────────────────────────────────────────────

def test_regime_alignment_high_when_high_fit_and_confidence():
    regime = _make_regime(confidence=1.0)
    candidate = _make_candidate(regime_fit=1.0)
    score = _score_regime_alignment(candidate, regime)
    assert score > 90.0


def test_regime_alignment_low_when_poor_fit():
    regime = _make_regime(confidence=0.5)
    candidate = _make_candidate(regime_fit=0.1)
    score = _score_regime_alignment(candidate, regime)
    assert score < 30.0


def test_iv_environment_premium_seller_high_iv():
    """Premium sellers benefit from high IV rank."""
    score = _score_iv_environment("iron_condor", iv_rank=80.0)
    assert score > 80.0


def test_iv_environment_premium_seller_low_iv():
    """Premium sellers score poorly in low IV environment."""
    score = _score_iv_environment("cash_secured_put", iv_rank=15.0)
    assert score < 35.0


def test_iv_environment_long_call_low_iv():
    """Long options buyers benefit from low IV."""
    score = _score_iv_environment("long_call", iv_rank=10.0)
    assert score > 80.0


def test_pop_sweet_spot():
    """65–85% POP → high score."""
    score = _score_probability_of_profit(72.0)
    assert score >= 85.0


def test_pop_very_high():
    """Very high POP (>95%) → slightly penalised (too safe = little edge)."""
    score = _score_probability_of_profit(97.0)
    assert score < 70.0


def test_pop_low():
    score = _score_probability_of_profit(30.0)
    assert score < 40.0


def test_risk_reward_1_to_1():
    assert _score_risk_reward(500.0, 500.0) >= 90.0


def test_risk_reward_poor():
    assert _score_risk_reward(100.0, 1000.0) < 40.0


def test_risk_reward_unlimited_upside():
    assert _score_risk_reward(float("inf"), 500.0) == 80.0


def test_kelly_score_zero():
    assert _score_kelly(0.0) == 0.0


def test_kelly_score_full():
    """0.25 Kelly (max allowed) → 100 score."""
    assert _score_kelly(0.25) == pytest.approx(100.0)


def test_event_risk_no_events():
    score = _score_event_risk(30, [])
    assert score == 80.0


def test_event_risk_high_impact_within_dte():
    score = _score_event_risk(30, [{"days_away": 10, "impact": "high"}])
    assert score == 55.0  # 80 - 25


def test_event_risk_multiple_events():
    events = [
        {"days_away": 5, "impact": "high"},
        {"days_away": 15, "impact": "medium"},
    ]
    score = _score_event_risk(30, events)
    assert score == 45.0  # 80 - 25 - 10


def test_time_decay_premium_seller_sweet_spot():
    score = _score_time_decay("iron_condor", 30)
    assert score == 90.0


def test_time_decay_premium_seller_too_short():
    score = _score_time_decay("cash_secured_put", 5)
    assert score == 50.0


# ── score_strategy (full integration) ────────────────────────────────────────

def test_score_strategy_returns_strategy_score():
    result = score_strategy(
        candidate=_make_candidate(),
        params=_make_params(),
        regime=_make_regime(),
        iv_rank=65.0,
        kelly_frac=0.10,
    )
    assert isinstance(result, StrategyScore)
    assert 0.0 <= result.composite <= 100.0


def test_score_strategy_breakdown_matches_fields():
    result = score_strategy(
        candidate=_make_candidate(),
        params=_make_params(),
        regime=_make_regime(),
        iv_rank=65.0,
        kelly_frac=0.10,
    )
    for key in result.breakdown:
        assert 0.0 <= result.breakdown[key] <= 100.0


def test_high_iv_rank_boosts_premium_seller_score():
    low_iv = score_strategy(
        _make_candidate("iron_condor"), _make_params("iron_condor"),
        _make_regime(), iv_rank=10.0, kelly_frac=0.10
    )
    high_iv = score_strategy(
        _make_candidate("iron_condor"), _make_params("iron_condor"),
        _make_regime(), iv_rank=85.0, kelly_frac=0.10
    )
    assert high_iv.composite > low_iv.composite


# ── rank_strategies ───────────────────────────────────────────────────────────

def test_rank_strategies_sorted_descending():
    scores = [
        StrategyScore("a", composite=60.0),
        StrategyScore("b", composite=80.0),
        StrategyScore("c", composite=70.0),
    ]
    ranked = rank_strategies(scores)
    composites = [s.composite for s in ranked]
    assert composites == sorted(composites, reverse=True)


def test_rank_strategies_single_item():
    scores = [StrategyScore("a", composite=55.0)]
    assert rank_strategies(scores) == scores
