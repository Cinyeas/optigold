from fastapi import APIRouter
from app.api.v1.endpoints import signals, market, settings, positions, notifications

router = APIRouter()
router.include_router(signals.router, prefix="/signals", tags=["signals"])
router.include_router(market.router, prefix="/market", tags=["market"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])
router.include_router(positions.router, prefix="/positions", tags=["positions"])
router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
