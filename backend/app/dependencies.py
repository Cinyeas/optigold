from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.base import async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
