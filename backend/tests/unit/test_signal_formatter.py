"""Unit tests for the signal formatter."""

import json
import pytest
from datetime import date
from app.quant.signal_formatter import (
    format_signal,
    FormattedSignal,
    _action_label,
    _confidence_label,
    _iv_label,
    _scenario_analysis,
)
from app.quant.market_regime import MarketRegime
from app.quant.parameter_engine import StrategyParameters
from app.quant.scoring_engine import StrategyScore


def _make_regime(regime: str = "low_vol_range") -> MarketRegime:
    return MarketRegime(
        regime=regime, bias="neutral", confidence=0.80,
        trend_signal="flat", vol_signal="low",
        momentum_signal="neutral", adx_signal="moderate",
        description="test regime",
    )


def _make_params(strategy: str = "cash_secured_put") -> StrategyParameters:
    p = StrategyParameters(strategy=strategy, instrument="GLD")
    p.strike_a = 215.0
    p.strike_b = 225.0
    p.expiry = date(2026, 4, 17)
    p.dte = 30
    p.quantity = 1
    p.premium_collected = 150.0
    p.max_profit = 150.0
    p.max_loss = 2000.0
    p.breakeven_a = 213.5
    p.breakeven_b = 226.5
    p.probability_of_profit = 72.0
    p.greeks = {"delta": -0.28, "gamma": 0.02, "theta": -0.05, "vega": 0.12, "rho": -0.01}
    return p


def _make_score(strategy: str = "cash_secured_put") -> StrategyScore:
    return StrategyScore(
        strategy=strategy,
        composite=68.5,
        regime_alignment=70.0,
        iv_environment=75.0,
        probability_of_profit=85.0,
        risk_reward=60.0,
        kelly_fraction=40.0,
        greeks_quality=55.0,
        event_risk=80.0,
        liquidity_proxy=85.0,
        time_decay_favorability=90.0,
        user_suitability=65.0,
    )


# ── format_signal ─────────────────────────────────────────────────────────────

def test_format_signal_returns_formatted_signal():
    fs = format_signal(
        strategy="cash_secured_put",
        params=_make_params(),
        score=_make_score(),
        regime=_make_regime(),
        iv_rank=55.0,
        iv_percentile=60.0,
        kelly_frac=0.08,
        spot=220.0,
        signal_id="SIG-TEST-001",
    )
    assert isinstance(fs, FormattedSignal)


def test_signal_id_preserved():
    fs = format_signal(
        strategy="cash_secured_put",
        params=_make_params(),
        score=_make_score(),
        regime=_make_regime(),
        iv_rank=55.0,
        iv_percentile=60.0,
        kelly_frac=0.08,
        spot=220.0,
        signal_id="SIG-UNIQUE-XYZ",
    )
    assert fs.signal_id == "SIG-UNIQUE-XYZ"


def test_plain_explanation_non_empty():
    fs = format_signal(
        strategy="cash_secured_put",
        params=_make_params(),
        score=_make_score(),
        regime=_make_regime(),
        iv_rank=55.0,
        iv_percentile=60.0,
        kelly_frac=0.08,
        spot=220.0,
        signal_id="SIG-001",
    )
    assert len(fs.plain_explanation) > 20


def test_detailed_reasoning_contains_score():
    fs = format_signal(
        strategy="cash_secured_put",
        params=_make_params(),
        score=_make_score(),
        regime=_make_regime(),
        iv_rank=55.0,
        iv_percentile=60.0,
        kelly_frac=0.08,
        spot=220.0,
        signal_id="SIG-001",
    )
    assert "68.5" in fs.detailed_reasoning or "68" in fs.detailed_reasoning


def test_greeks_included_in_signal():
    fs = format_signal(
        strategy="cash_secured_put",
        params=_make_params(),
        score=_make_score(),
        regime=_make_regime(),
        iv_rank=55.0, iv_percentile=60.0,
        kelly_frac=0.08, spot=220.0,
        signal_id="SIG-001",
    )
    assert "delta" in fs.greeks
    assert "theta" in fs.greeks


def test_score_breakdown_in_signal():
    fs = format_signal(
        strategy="cash_secured_put",
        params=_make_params(),
        score=_make_score(),
        regime=_make_regime(),
        iv_rank=55.0, iv_percentile=60.0,
        kelly_frac=0.08, spot=220.0,
        signal_id="SIG-001",
    )
    assert "regime_alignment" in fs.score_breakdown


def test_confidence_label_high():
    fs = format_signal(
        strategy="cash_secured_put",
        params=_make_params(),
        score=StrategyScore("cash_secured_put", composite=75.0),
        regime=_make_regime(),
        iv_rank=55.0, iv_percentile=60.0,
        kelly_frac=0.08, spot=220.0,
        signal_id="SIG-001",
    )
    assert fs.confidence == "high"


def test_confidence_label_low():
    fs = format_signal(
        strategy="cash_secured_put",
        params=_make_params(),
        score=StrategyScore("cash_secured_put", composite=40.0),
        regime=_make_regime(),
        iv_rank=55.0, iv_percentile=60.0,
        kelly_frac=0.08, spot=220.0,
        signal_id="SIG-001",
    )
    assert fs.confidence == "low"


def test_alt_signal_included():
    alt = {"strategy": "bull_put_spread", "composite_score": 62.0}
    fs = format_signal(
        strategy="cash_secured_put",
        params=_make_params(),
        score=_make_score(),
        regime=_make_regime(),
        iv_rank=55.0, iv_percentile=60.0,
        kelly_frac=0.08, spot=220.0,
        signal_id="SIG-001",
        alt_candidate=alt,
    )
    assert fs.alt_signal is not None
    assert fs.alt_signal["strategy"] == "bull_put_spread"


def test_scenarios_populated():
    fs = format_signal(
        strategy="cash_secured_put",
        params=_make_params(),
        score=_make_score(),
        regime=_make_regime(),
        iv_rank=55.0, iv_percentile=60.0,
        kelly_frac=0.08, spot=220.0,
        signal_id="SIG-001",
    )
    assert len(fs.scenarios.bull_case) > 5
    assert len(fs.scenarios.base_case) > 5
    assert len(fs.scenarios.bear_case) > 5


def test_to_db_dict_serializable():
    fs = format_signal(
        strategy="cash_secured_put",
        params=_make_params(),
        score=_make_score(),
        regime=_make_regime(),
        iv_rank=55.0, iv_percentile=60.0,
        kelly_frac=0.08, spot=220.0,
        signal_id="SIG-001",
    )
    db_dict = fs.to_db_dict()
    # Verify JSON fields can be parsed back
    assert isinstance(json.loads(db_dict["greeks_json"]), dict)
    assert isinstance(json.loads(db_dict["score_breakdown_json"]), dict)
    assert db_dict["id"] == "SIG-001"


# ── Helper functions ──────────────────────────────────────────────────────────

def test_confidence_label_thresholds():
    assert _confidence_label(80.0) == "high"
    assert _confidence_label(60.0) == "medium"
    assert _confidence_label(40.0) == "low"
    assert _confidence_label(72.0) == "high"
    assert _confidence_label(71.9) == "medium"


def test_iv_label():
    assert _iv_label(75) == "elevated"
    assert _iv_label(50) == "normal"
    assert _iv_label(20) == "compressed"


def test_action_label_iron_condor():
    p = _make_params("iron_condor")
    label = _action_label("iron_condor", p)
    assert "IRON CONDOR" in label
    assert "215" in label


def test_scenario_analysis_for_premium_seller():
    p = _make_params("cash_secured_put")
    scenarios = _scenario_analysis("cash_secured_put", p, spot=220.0)
    assert "rallies" in scenarios.bull_case.lower() or "premium" in scenarios.bull_case.lower()
    assert "drops" in scenarios.bear_case.lower() or "down" in scenarios.bear_case.lower() or "falls" in scenarios.bear_case.lower()
