from __future__ import annotations

"""Position review engine — evaluates open positions and flags action needed."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Optional


class ReviewTrigger(str, Enum):
    SCHEDULED_WEEKLY = "scheduled_weekly"
    DTE_THRESHOLD = "dte_threshold"
    PRICE_BREACH = "price_breach"
    IV_SPIKE = "iv_spike"
    REGIME_CHANGE = "regime_change"
    LOSS_LIMIT = "loss_limit"
    MANUAL = "manual"


class ReviewConclusion(str, Enum):
    HOLD = "hold"
    CLOSE = "close"
    ROLL = "roll"
    ADJUST = "adjust"
    HEDGE = "hedge"
    MONITOR = "monitor"


@dataclass
class ReviewResult:
    trigger: ReviewTrigger
    conclusion: ReviewConclusion
    reasoning: str
    urgency: str          # "low", "medium", "high", "critical"
    suggested_action: Optional[str] = None
    new_signal_needed: bool = False


def check_position_review(
    position: dict[str, Any],
    current_snapshot: dict[str, Any],
    current_regime: str,
) -> ReviewResult:
    """
    Analyse an open position and recommend a course of action.

    Args:
        position: Dict with position fields (strategy, entry_price, expiry,
                  strike_a, strike_b, max_loss, quantity, etc.).
        current_snapshot: Latest market data dict.
        current_regime: Detected regime string.

    Returns:
        ReviewResult with the most actionable trigger/conclusion pair.
    """
    results: list[ReviewResult] = []

    # ── 1. DTE check ──────────────────────────────────────────────────────────
    expiry = position.get("expiry")
    if expiry:
        if isinstance(expiry, str):
            expiry = date.fromisoformat(expiry)
        dte = (expiry - date.today()).days
        if dte <= 0:
            results.append(
                ReviewResult(
                    trigger=ReviewTrigger.DTE_THRESHOLD,
                    conclusion=ReviewConclusion.CLOSE,
                    reasoning="Position has expired or expires today — close immediately.",
                    urgency="critical",
                    suggested_action="Close all legs at market.",
                )
            )
        elif dte <= 5:
            results.append(
                ReviewResult(
                    trigger=ReviewTrigger.DTE_THRESHOLD,
                    conclusion=ReviewConclusion.CLOSE,
                    reasoning=f"Only {dte} DTE remaining. Gamma risk is elevated. "
                              "Close or roll to avoid pin risk.",
                    urgency="high",
                    suggested_action=f"Close position with {dte} DTE remaining.",
                )
            )
        elif dte <= 14:
            results.append(
                ReviewResult(
                    trigger=ReviewTrigger.DTE_THRESHOLD,
                    conclusion=ReviewConclusion.MONITOR,
                    reasoning=f"{dte} DTE — entering accelerated theta decay zone. "
                              "Consider closing at 50% max profit.",
                    urgency="medium",
                )
            )

    # ── 2. Price vs breakeven check ───────────────────────────────────────────
    spot = float(current_snapshot.get("gld_price") or 0)
    breakeven_a = position.get("breakeven_a")
    breakeven_b = position.get("breakeven_b")
    strategy = position.get("strategy", "")

    if spot and breakeven_a:
        if strategy in ("cash_secured_put", "bull_put_spread") and spot < breakeven_a:
            results.append(
                ReviewResult(
                    trigger=ReviewTrigger.PRICE_BREACH,
                    conclusion=ReviewConclusion.CLOSE,
                    reasoning=f"GLD ${spot:.2f} has breached put breakeven ${breakeven_a:.2f}. "
                              "Position is at a loss.",
                    urgency="high",
                    suggested_action="Close the short put position to limit loss.",
                    new_signal_needed=True,
                )
            )
        elif strategy == "bear_call_spread" and spot > breakeven_a:
            results.append(
                ReviewResult(
                    trigger=ReviewTrigger.PRICE_BREACH,
                    conclusion=ReviewConclusion.CLOSE,
                    reasoning=f"GLD ${spot:.2f} breached call breakeven ${breakeven_a:.2f}.",
                    urgency="high",
                    suggested_action="Close the short call spread to limit loss.",
                    new_signal_needed=True,
                )
            )
        elif strategy == "iron_condor" and breakeven_b and (
            spot < breakeven_a or spot > breakeven_b
        ):
            results.append(
                ReviewResult(
                    trigger=ReviewTrigger.PRICE_BREACH,
                    conclusion=ReviewConclusion.ADJUST,
                    reasoning=(
                        f"Iron Condor breached: GLD ${spot:.2f} outside "
                        f"[${breakeven_a:.2f}, ${breakeven_b:.2f}]."
                    ),
                    urgency="high",
                    suggested_action="Close the tested side; consider rolling the untested side.",
                    new_signal_needed=True,
                )
            )

    # ── 3. IV spike check ─────────────────────────────────────────────────────
    iv_rank = float(current_snapshot.get("gld_iv_rank") or 50)
    entry_iv = float(position.get("entry_iv_rank") or iv_rank)

    if iv_rank > entry_iv + 30 and iv_rank >= 70:
        results.append(
            ReviewResult(
                trigger=ReviewTrigger.IV_SPIKE,
                conclusion=ReviewConclusion.HEDGE,
                reasoning=(
                    f"IV Rank spiked to {iv_rank:.0f} (was ~{entry_iv:.0f} at entry). "
                    "Long options may now be worth buying as protection."
                ),
                urgency="medium",
                suggested_action="Consider adding long put hedge or rolling to wider strikes.",
            )
        )

    # ── 4. Regime change check ────────────────────────────────────────────────
    entry_regime = position.get("entry_regime", current_regime)
    if entry_regime != current_regime:
        results.append(
            ReviewResult(
                trigger=ReviewTrigger.REGIME_CHANGE,
                conclusion=ReviewConclusion.MONITOR,
                reasoning=(
                    f"Market regime changed from '{entry_regime}' to '{current_regime}'. "
                    "Strategy may no longer be optimal."
                ),
                urgency="medium",
                suggested_action="Review position sizing; consider closing if regime is adverse.",
                new_signal_needed=True,
            )
        )

    # ── 5. Loss limit check ───────────────────────────────────────────────────
    max_loss = float(position.get("max_loss") or 0)
    entry_price = float(position.get("entry_price") or 0)
    if max_loss > 0 and entry_price > 0 and spot:
        unrealised_loss_pct = (entry_price - spot) / entry_price if strategy in (
            "long_call", "long_put", "long_straddle"
        ) else 0.0
        if unrealised_loss_pct <= -0.50:  # 50% of premium lost
            results.append(
                ReviewResult(
                    trigger=ReviewTrigger.LOSS_LIMIT,
                    conclusion=ReviewConclusion.CLOSE,
                    reasoning="Position has lost more than 50% of premium. Stop-loss triggered.",
                    urgency="critical",
                    suggested_action="Close position to preserve capital.",
                )
            )

    # ── Select highest-urgency result ─────────────────────────────────────────
    urgency_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    if results:
        results.sort(key=lambda r: urgency_rank.get(r.urgency, 0), reverse=True)
        return results[0]

    # Default: hold
    return ReviewResult(
        trigger=ReviewTrigger.SCHEDULED_WEEKLY,
        conclusion=ReviewConclusion.HOLD,
        reasoning="No adverse conditions detected. Position within expected parameters.",
        urgency="low",
    )
