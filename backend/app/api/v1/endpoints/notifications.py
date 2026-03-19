"""Push notification endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.schemas.notification import DeviceTokenRegister, DeviceTokenResponse
from app.services.notification_service import register_device_token

router = APIRouter()


@router.post("/register", response_model=DeviceTokenResponse, status_code=201)
async def register_token(
    payload: DeviceTokenRegister,
    db: AsyncSession = Depends(get_db),
):
    """Register or reactivate a push notification device token."""
    token = await register_device_token(db, payload.token, payload.platform)
    return token
