"""Service layer for position review orchestration."""

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db.user_position import UserPosition
from app.models.db.signal_review import SignalReview
from app.quant.review_engine import check_position_review, ReviewResult
from app.services.market_data_service import get_gld_snapshot
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def review_open_positions(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Run review engine on all open positions and persist results.

    Returns a list of review dicts with position_id and review details.
    """
    result = await db.execute(
        select(UserPosition).where(UserPosition.status == "open")
    )
    positions = result.scalars().all()

    if not positions:
        logger.info("No open positions to review.")
        return []

    snapshot = get_gld_snapshot()
    current_regime = snapshot.get("market_regime", "choppy")

    reviews = []
    for pos in positions:
        pos_dict = {
            "id": pos.id,
            "signal_id": pos.signal_id,
            "strategy": pos.strategy,
            "strike_a": pos.strike_a,
            "strike_b": pos.strike_b,
            "expiry": pos.expiry,
            "entry_price": pos.entry_price,
            "quantity": pos.quantity,
        }

        review_result: ReviewResult = check_position_review(
            position=pos_dict,
            current_snapshot=snapshot,
            current_regime=current_regime,
        )

        # Persist review
        sr = SignalReview(
            original_signal_id=pos.signal_id,
            position_id=pos.id,
            reviewed_at=datetime.utcnow(),
            trigger=review_result.trigger.value,
            conclusion=review_result.conclusion.value,
            reasoning=review_result.reasoning,
            urgency=review_result.urgency,
        )
        db.add(sr)

        reviews.append({
            "position_id": pos.id,
            "trigger": review_result.trigger.value,
            "conclusion": review_result.conclusion.value,
            "reasoning": review_result.reasoning,
            "urgency": review_result.urgency,
            "suggested_action": review_result.suggested_action,
            "new_signal_needed": review_result.new_signal_needed,
        })

        logger.info(
            "Position %d reviewed: %s → %s (%s)",
            pos.id,
            review_result.trigger.value,
            review_result.conclusion.value,
            review_result.urgency,
        )

    await db.flush()
    return reviews
