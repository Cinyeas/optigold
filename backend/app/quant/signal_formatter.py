from __future__ import annotations

"""Format raw quant output into structured signals for the Flutter app."""

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any, Optional

from app.quant.parameter_engine import StrategyParameters
from app.quant.scoring_engine import StrategyScore
from app.quant.market_regime import MarketRegime


@dataclass
class ScenarioAnalysis:
    """Three-scenario outcome analysis for a trade."""

    bull_case: str = ""
    base_case: str = ""
    bear_case: str = ""


@dataclass
class FormattedSignal:
    """Complete structured signal ready for DB storage and API delivery."""

    signal_id: str
    generated_at: datetime
    action: str          # e.g. "SELL PUT SPREAD"
    instrument: str = "GLD"
    strike_a: Optional[float] = None
    strike_b: Optional[float] = None
    expiry: Optional[date] = None
    quantity: int = 1
    premium_collected: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven_a: Optional[float] = None
    breakeven_b: Optional[float] = None
    probability_of_profit: float = 0.0
    expected_value: float = 0.0
    kelly_fraction: float = 0.0
    composite_score: float = 0.0
    confidence: str = "medium"      # "low", "medium", "high"
    iv_rank: float = 0.0
    iv_percentile: float = 0.0
    market_regime: str = ""
    market_bias: str = ""
    plain_explanation: str = ""
    detailed_reasoning: str = ""
    greeks: dict[str, float] = field(default_factory=dict)
    score_breakdown: dict[str, float] = field(default_factory=dict)
    scenarios: ScenarioAnalysis = field(default_factory=ScenarioAnalysis)
    alt_signal: Optional[dict[str, Any]] = None

    def to_db_dict(self) -> dict[str, Any]:
        """Convert to a flat dict suitable for DB insertion."""
        return {
            "id": self.signal_id,
            "generated_at": self.generated_at,
            "action": self.action,
            "instrument": self.instrument,
            "strike_a": self.strike_a,
            "strike_b": self.strike_b,
            "expiry": self.expiry,
            "quantity": self.quantity,
            "premium_collected": self.premium_collected,
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "breakeven_a": self.breakeven_a,
            "breakeven_b": self.breakeven_b,
            "probability_of_profit": self.probability_of_profit,
            "expected_value": self.expected_value,
            "kelly_fraction": self.kelly_fraction,
            "composite_score": self.composite_score,
            "confidence": self.confidence,
            "iv_rank": self.iv_rank,
            "iv_percentile": self.iv_percentile,
            "market_regime": self.market_regime,
            "market_bias": self.market_bias,
            "reasoning_plain": self.plain_explanation,
            "reasoning_detail": self.detailed_reasoning,
            "greeks_json": json.dumps(self.greeks),
            "score_breakdown_json": json.dumps(self.score_breakdown),
            "alt_signal_json": json.dumps(self.alt_signal) if self.alt_signal else None,
        }


def _action_label(strategy: str, params: StrategyParameters) -> str:
    """Generate a short action label for the signal."""
    labels = {
        "cash_secured_put": f"SELL PUT ${params.strike_a:.0f}",
        "covered_call": f"SELL CALL ${params.strike_a:.0f}",
        "bull_put_spread": (
            f"SELL PUT SPREAD ${params.strike_b:.0f}/${params.strike_a:.0f}"
            if params.strike_b else f"SELL PUT SPREAD"
        ),
        "bear_call_spread": (
            f"SELL CALL SPREAD ${params.strike_a:.0f}/${params.strike_b:.0f}"
            if params.strike_b else f"SELL CALL SPREAD"
        ),
        "iron_condor": (
            f"IRON CONDOR ${params.strike_a:.0f}/${params.strike_b:.0f}"
            if params.strike_b else "IRON CONDOR"
        ),
        "iron_butterfly": f"IRON BUTTERFLY ${params.strike_a:.0f}",
        "long_call": f"BUY CALL ${params.strike_a:.0f}",
        "long_put": f"BUY PUT ${params.strike_a:.0f}",
        "long_straddle": f"BUY STRADDLE ${params.strike_a:.0f}",
        "short_straddle": f"SELL STRADDLE ${params.strike_a:.0f}",
    }
    return labels.get(strategy, strategy.upper().replace("_", " "))


def _plain_explanation(
    strategy: str,
    params: StrategyParameters,
    regime: MarketRegime,
    iv_rank: float,
    score: StrategyScore,
) -> str:
    """Generate a 2–4 sentence plain-English explanation."""
    sa = params.strike_a or 0.0
    sb = params.strike_b or sa
    ba = params.breakeven_a or 0.0
    bb = params.breakeven_b or 0.0
    prem_per_share = params.premium_collected / max(params.quantity, 1) / 100

    if strategy == "cash_secured_put":
        return (
            f"Sell the GLD {params.expiry} ${sa:.0f} put for ~${prem_per_share:.2f} per share. "
            f"You keep the full premium if GLD stays above ${sa:.0f} at expiry. "
            f"IV Rank is {iv_rank:.0f}/100, making option premium {_iv_label(iv_rank)}. "
            f"Market is {regime.bias} with a {regime.regime.replace('_', ' ')} setup."
        )
    if strategy == "bull_put_spread":
        return (
            f"Sell the ${sb:.0f}/${sa:.0f} put spread, "
            f"collecting ~${prem_per_share:.2f} per share net credit. "
            f"Max profit ${params.max_profit:.0f} if GLD stays above ${sb:.0f}; "
            f"max loss capped at ${params.max_loss:.0f}. "
            f"Probability of profit: ~{params.probability_of_profit:.0f}%."
        )
    if strategy == "iron_condor":
        return (
            f"Open an Iron Condor with short strikes at ${sa:.0f} (put) / ${sb:.0f} (call). "
            f"Collect ~${params.premium_collected:.0f} total credit. "
            f"Profit as long as GLD stays between ${ba:.0f} and ${bb:.0f} at expiry."
        )
    if strategy == "long_call":
        paid_per_share = params.premium_paid / max(params.quantity, 1) / 100
        return (
            f"Buy the GLD {params.expiry} ${sa:.0f} call for ~${paid_per_share:.2f} per share. "
            f"Bullish play — unlimited upside above ${ba:.0f}. "
            f"Max loss is the premium paid (${params.premium_paid:.0f} total)."
        )
    if strategy == "long_put":
        paid_per_share = params.premium_paid / max(params.quantity, 1) / 100
        return (
            f"Buy the GLD {params.expiry} ${sa:.0f} put for ~${paid_per_share:.2f} per share. "
            f"Bearish hedge — profits if GLD falls below ${ba:.0f}. "
            f"Max loss is the premium paid (${params.premium_paid:.0f} total)."
        )
    return (
        f"Execute a {strategy.replace('_', ' ')} on GLD. "
        f"Composite score {score.composite:.0f}/100 — {_confidence_label(score.composite)} setup. "
        f"Market regime: {regime.regime.replace('_', ' ')} ({regime.bias})."
    )


def _detailed_reasoning(
    strategy: str,
    score: StrategyScore,
    regime: MarketRegime,
    iv_rank: float,
    params: StrategyParameters,
) -> str:
    """Build a structured detailed reasoning string."""
    lines = [
        f"Strategy: {strategy.replace('_', ' ').title()}",
        f"Composite Score: {score.composite:.1f}/100",
        "",
        "Score Breakdown:",
        *[f"  {k.replace('_', ' ').title()}: {v:.1f}" for k, v in score.breakdown.items()],
        "",
        f"Market Regime: {regime.regime} (bias={regime.bias}, "
        f"confidence={regime.confidence:.0%})",
        f"IV Rank: {iv_rank:.0f}/100 — {_iv_label(iv_rank)} premium environment",
        f"Trend: {regime.trend_signal}, Momentum: {regime.momentum_signal}, "
        f"Volatility: {regime.vol_signal}",
        "",
        f"Position Details:",
        f"  Expiry: {params.expiry} ({params.dte} DTE)",
        f"  Max Profit: ${params.max_profit:,.0f}",
        f"  Max Loss: ${params.max_loss:,.0f}",
        f"  Breakeven: ${params.breakeven_a:.2f}"
        + (f" / ${params.breakeven_b:.2f}" if params.breakeven_b else ""),
        f"  P(Profit): {params.probability_of_profit:.0f}%",
    ]
    if params.greeks:
        lines += [
            "",
            "Greeks (per contract):",
            f"  Delta: {params.greeks.get('delta', 0):.4f}",
            f"  Gamma: {params.greeks.get('gamma', 0):.6f}",
            f"  Theta: ${params.greeks.get('theta', 0):.4f}/day",
            f"  Vega:  ${params.greeks.get('vega', 0):.4f}/1% IV",
        ]
    return "\n".join(lines)


def _scenario_analysis(
    strategy: str, params: StrategyParameters, spot: float
) -> ScenarioAnalysis:
    """Generate three-scenario analysis."""
    premium_sellers = {
        "cash_secured_put", "covered_call", "bull_put_spread",
        "bear_call_spread", "iron_condor", "iron_butterfly",
    }
    if strategy in premium_sellers:
        bull = (
            f"GLD rallies to ${spot * 1.05:.0f} (+5%): All short options expire worthless. "
            f"Full premium collected: +${params.max_profit:,.0f}."
        )
        base = (
            f"GLD stays near ${spot:.0f}: Position expires near-worthless. "
            f"Collect ~{0.75 * params.max_profit / max(params.max_profit, 1):.0%} of max profit by 21 DTE."
        )
        bear = (
            f"GLD drops to ${spot * 0.95:.0f} (-5%): "
            + (
                f"Put spread approaches max loss of ${params.max_loss:,.0f}. "
                "Consider closing early at 2× premium collected."
                if "put" in strategy
                else f"Position may see increased mark-to-market loss. Max loss: ${params.max_loss:,.0f}."
            )
        )
    else:
        bull = (
            f"GLD rallies to ${spot * 1.08:.0f} (+8%): "
            f"Long option gains in value. Estimated P&L: +${params.max_profit * 0.6:,.0f}."
        )
        base = (
            f"GLD stays near ${spot:.0f}: Option loses time value. "
            f"Consider closing at 21 DTE to avoid accelerating theta decay."
        )
        bear = (
            f"GLD falls to ${spot * 0.92:.0f} (-8%): "
            f"Max loss scenario — premium fully eroded: -${params.max_loss:,.0f}."
        )
    return ScenarioAnalysis(bull_case=bull, base_case=base, bear_case=bear)


def _confidence_label(score: float) -> str:
    if score >= 72:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _iv_label(iv_rank: float) -> str:
    if iv_rank >= 70:
        return "elevated"
    if iv_rank >= 40:
        return "normal"
    return "compressed"


def format_signal(
    strategy: str,
    params: StrategyParameters,
    score: StrategyScore,
    regime: MarketRegime,
    iv_rank: float,
    iv_percentile: float,
    kelly_frac: float,
    spot: float,
    signal_id: str,
    alt_candidate: Optional[dict[str, Any]] = None,
) -> FormattedSignal:
    """
    Assemble a complete FormattedSignal from quant engine outputs.

    Args:
        strategy:       Strategy name.
        params:         Concrete option parameters.
        score:          Multi-dim StrategyScore.
        regime:         Detected market regime.
        iv_rank:        Current IV Rank (0–100).
        iv_percentile:  Current IV Percentile (0–100).
        kelly_frac:     Adjusted Kelly fraction.
        spot:           Current GLD spot price.
        signal_id:      Unique signal identifier.
        alt_candidate:  Optional alternative strategy dict.

    Returns:
        FormattedSignal ready for DB persistence and API delivery.
    """
    from app.quant.kelly_sizer import expected_value as _ev

    win_prob = params.probability_of_profit / 100
    ev = _ev(win_prob, params.max_profit, params.max_loss) if params.max_loss < float("inf") else 0.0

    return FormattedSignal(
        signal_id=signal_id,
        generated_at=datetime.utcnow(),
        action=_action_label(strategy, params),
        instrument="GLD",
        strike_a=params.strike_a,
        strike_b=params.strike_b,
        expiry=params.expiry,
        quantity=params.quantity,
        premium_collected=params.premium_collected,
        max_profit=params.max_profit if params.max_profit != float("inf") else -1.0,
        max_loss=params.max_loss if params.max_loss != float("inf") else -1.0,
        breakeven_a=params.breakeven_a,
        breakeven_b=params.breakeven_b,
        probability_of_profit=params.probability_of_profit,
        expected_value=round(ev, 2),
        kelly_fraction=round(kelly_frac, 4),
        composite_score=score.composite,
        confidence=_confidence_label(score.composite),
        iv_rank=round(iv_rank, 1),
        iv_percentile=round(iv_percentile, 1),
        market_regime=regime.regime,
        market_bias=regime.bias,
        plain_explanation=_plain_explanation(strategy, params, regime, iv_rank, score),
        detailed_reasoning=_detailed_reasoning(strategy, score, regime, iv_rank, params),
        greeks=params.greeks,
        score_breakdown=score.breakdown,
        scenarios=_scenario_analysis(strategy, params, spot),
        alt_signal=alt_candidate,
    )
