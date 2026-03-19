"""Market data endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db
from app.models.db.market_snapshot import MarketSnapshot
from app.models.schemas.market import MarketSnapshotResponse, IVRankResponse
from app.services.market_data_service import get_gld_snapshot

router = APIRouter()


@router.get("/snapshot", response_model=MarketSnapshotResponse)
async def get_snapshot(db: AsyncSession = Depends(get_db)):
    """Return the latest market snapshot (fresh synthetic data)."""
    snap = get_gld_snapshot()

    # Persist to DB — filter out internal keys not in the DB model
    _db_fields = {c.key for c in MarketSnapshot.__table__.columns} - {"id"}
    ms = MarketSnapshot(**{k: v for k, v in snap.items() if k in _db_fields})
    db.add(ms)
    return snap


@router.get("/iv-rank", response_model=IVRankResponse)
async def get_iv_rank(db: AsyncSession = Depends(get_db)):
    """Return IV Rank, IV Percentile, and IV premium ratio for GLD."""
    snap = get_gld_snapshot()
    return IVRankResponse(
        symbol="GLD",
        iv_rank=snap["gld_iv_rank"],
        iv_percentile=snap["gld_iv_percentile"],
        current_iv=snap["gld_atm_iv"],
        hv_20d=snap["gld_hv_20d"],
        iv_premium_ratio=snap["iv_premium_ratio"],
        captured_at=snap["captured_at"],
    )
