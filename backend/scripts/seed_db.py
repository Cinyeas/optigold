"""
Seed script: insert default UserProfile (id=1) if not present.

Run from the backend directory:
    python -m scripts.seed_db
"""

import asyncio
import sys
import os

# Ensure the backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.models.db.base import create_all_tables, async_session_maker
from app.models.db.user_profile import UserProfile
from app.utils.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger("seed_db")


async def seed() -> None:
    logger.info("Creating tables if needed...")
    await create_all_tables()

    async with async_session_maker() as session:
        result = await session.execute(select(UserProfile).where(UserProfile.id == 1))
        existing = result.scalar_one_or_none()

        if existing:
            logger.info("Default UserProfile already exists — skipping.")
            return

        profile = UserProfile(
            id=1,
            capital=50_000.0,
            max_loss_per_trade=2_500.0,
            accepts_options=True,
            accepts_margin=False,
            accepts_unlimited_risk=False,
            accepts_multi_leg=False,
            time_horizon="monthly",
            experience_level="beginner",
            risk_multiplier=0.5,
            notifications_enabled=True,
        )
        session.add(profile)
        await session.commit()
        logger.info("Default UserProfile seeded: capital=50000, time_horizon=monthly.")


if __name__ == "__main__":
    asyncio.run(seed())
