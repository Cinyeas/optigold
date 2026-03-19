from __future__ import annotations

"""
APScheduler background jobs for OptiGold.

Phase 1: Scheduler is defined but jobs are lightweight stubs.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.utils.logging_config import get_logger

logger = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _refresh_market_snapshot() -> None:
    """Refresh market snapshot every 15 minutes during trading hours."""
    from app.utils.market_hours import is_market_open
    from app.services.market_data_service import get_gld_snapshot

    if not is_market_open():
        return
    snap = get_gld_snapshot()
    logger.debug("Scheduled snapshot refresh: GLD=%.2f", snap.get("gld_price", 0))


async def _run_signal_generation() -> None:
    """
    Generate a new signal at 9:35am and 3:45pm ET on trading days.
    Uses a real DB session for persistence.
    """
    from app.utils.market_hours import is_trading_day
    from app.models.db.base import async_session_maker
    from app.services.signal_service import generate_signal

    if not is_trading_day():
        return

    async with async_session_maker() as session:
        try:
            sig = await generate_signal(session)
            await session.commit()
            logger.info("Scheduled signal generated: %s", sig.signal_id)
        except Exception as exc:
            await session.rollback()
            logger.error("Scheduled signal generation failed: %s", exc)


async def _run_position_review() -> None:
    """Review open positions every weekday at market open."""
    from app.utils.market_hours import is_trading_day
    from app.models.db.base import async_session_maker
    from app.services.review_service import review_open_positions

    if not is_trading_day():
        return

    async with async_session_maker() as session:
        try:
            results = await review_open_positions(session)
            await session.commit()
            logger.info("Scheduled review completed: %d positions reviewed.", len(results))
        except Exception as exc:
            await session.rollback()
            logger.error("Scheduled position review failed: %s", exc)


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="America/New_York")

        # Market snapshot refresh every 15 minutes
        _scheduler.add_job(
            _refresh_market_snapshot,
            trigger=IntervalTrigger(minutes=15),
            id="market_snapshot",
            replace_existing=True,
        )

        # Signal generation: 9:35 AM and 3:45 PM ET on weekdays
        _scheduler.add_job(
            _run_signal_generation,
            trigger=CronTrigger(day_of_week="mon-fri", hour=9, minute=35),
            id="signal_morning",
            replace_existing=True,
        )
        _scheduler.add_job(
            _run_signal_generation,
            trigger=CronTrigger(day_of_week="mon-fri", hour=15, minute=45),
            id="signal_afternoon",
            replace_existing=True,
        )

        # Position review: 9:31 AM ET on weekdays
        _scheduler.add_job(
            _run_position_review,
            trigger=CronTrigger(day_of_week="mon-fri", hour=9, minute=31),
            id="position_review",
            replace_existing=True,
        )

    return _scheduler


def start_scheduler() -> None:
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        logger.info("Scheduler started.")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
