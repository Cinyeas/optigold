"""User settings / profile endpoints."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db
from app.models.db.user_profile import UserProfile
from app.models.schemas.settings import UserProfileResponse, UserProfileUpdate

router = APIRouter()


async def _get_profile(db: AsyncSession) -> UserProfile:
    result = await db.execute(select(UserProfile).where(UserProfile.id == 1))
    profile = result.scalar_one_or_none()
    if profile is None:
        # Auto-create default profile
        profile = UserProfile(id=1)
        db.add(profile)
        await db.flush()
    return profile


@router.get("/", response_model=UserProfileResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Fetch the current user profile / risk settings."""
    return await _get_profile(db)


@router.put("/", response_model=UserProfileResponse)
async def update_settings(
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update one or more user profile fields."""
    profile = await _get_profile(db)
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    profile.updated_at = datetime.utcnow()
    await db.flush()
    return profile
