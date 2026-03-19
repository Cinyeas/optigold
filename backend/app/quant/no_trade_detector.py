from __future__ import annotations

"""
No-trade detector — determines whether current conditions warrant
a "do not trade" recommendation instead of a strategy signal.

"Not trading" is a first-class outcome, not a fallback.
"""

from dataclasses import dataclass

from app.quant.market_regime import MarketRegime


@dataclass
class NoTradeSignal:
    """Signals that the system recommends no trade at this time."""

    reason_plain: str   # User-facing plain language explanation
    reason_code: str    # Machine-readable: "low_iv" | "low_confidence" |
                        #                   "overexposed" | "choppy_undecided"
    allow_reference: bool  # If True, show A/B strategies as "for reference only"


def check_no_trade(
    regime: MarketRegime,
    iv_rank: float,
    open_positions_count: int,
    daily_move_pct: float,
    candidate_strategy_names: list[str],
) -> NoTradeSignal | None:
    """
    Evaluate whether a no-trade recommendation should be issued.

    Rules are evaluated in priority order. First matching rule wins.

    Args:
        regime:                   Detected MarketRegime.
        iv_rank:                  Current IV Rank (0–100).
        open_positions_count:     Number of user's currently open positions.
        daily_move_pct:           GLD 24h price change percent (abs value).
        candidate_strategy_names: Strategy names that survived eligibility gate.

    Returns:
        NoTradeSignal if no-trade is recommended, else None.
    """

    # Rule 1: User already has 2+ open positions — risk is concentrated
    if open_positions_count >= 2:
        return NoTradeSignal(
            reason_plain=(
                "您已持有 2 笔以上未平仓头寸。"
                "建议优先管理现有持仓，再考虑新入场。"
            ),
            reason_code="overexposed",
            allow_reference=False,
        )

    # Rule 2: Regime confidence too low — no clear directional edge
    if regime.confidence < 0.40:
        return NoTradeSignal(
            reason_plain=(
                "当前市场方向信号不够清晰（置信度低于 40%）。"
                "强行入场的胜算与随机相当，建议等待。"
            ),
            reason_code="low_confidence",
            allow_reference=False,
        )

    # Rule 3: IV Rank very low AND all surviving candidates are premium sellers
    # (buyers benefit from low IV, so only trigger when sellers would be forced)
    _PREMIUM_SELLERS = {
        "cash_secured_put", "covered_call", "bull_put_spread",
        "bear_call_spread", "iron_condor", "iron_butterfly", "short_straddle",
    }
    all_sellers = all(s in _PREMIUM_SELLERS for s in candidate_strategy_names)
    if iv_rank < 20 and all_sellers and regime.regime not in ("crash_risk", "strong_trend_down"):
        return NoTradeSignal(
            reason_plain=(
                f"当前 IV Rank 极低（{iv_rank:.0f}），期权权利金过于便宜。"
                "卖出溢价的风险回报比不划算，建议等待 IV 回升后再入场。"
            ),
            reason_code="low_iv",
            allow_reference=True,
        )

    # Rule 4: Large intraday move + regime still undecided
    # (position entered during a spike risks being on the wrong side)
    if daily_move_pct >= 2.0 and regime.trend_signal == "neutral" and regime.confidence < 0.60:
        return NoTradeSignal(
            reason_plain=(
                f"GLD 今日波动幅度较大（{daily_move_pct:.1f}%），"
                "但市场方向尚未确认。等待价格稳定后再评估。"
            ),
            reason_code="choppy_undecided",
            allow_reference=False,
        )

    return None
