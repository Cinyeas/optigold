"""Signal endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.dependencies import get_db
from app.models.db.signal import Signal
from app.models.schemas.signal import SignalResponse, SignalListItem, SignalListResponse
from app.services.signal_service import generate_signal

router = APIRouter()


def _enrich_signal(sig: Signal) -> dict:
    """Parse JSON blob fields for API response."""
    d = {c.name: getattr(sig, c.name) for c in sig.__table__.columns}
    for json_field, target in [
        ("greeks_json", "greeks"),
        ("score_breakdown_json", "score_breakdown"),
        ("alt_signal_json", "alt_signal"),
    ]:
        raw = d.pop(json_field, None)
        d[target] = json.loads(raw) if raw else None
    return d


@router.get("/latest", response_model=SignalResponse)
async def get_latest_signal(db: AsyncSession = Depends(get_db)):
    """Return the most recently generated signal."""
    result = await db.execute(
        select(Signal).order_by(Signal.generated_at.desc()).limit(1)
    )
    sig = result.scalar_one_or_none()
    if sig is None:
        raise HTTPException(status_code=404, detail="No signals found. Try POST /refresh.")
    return _enrich_signal(sig)


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(signal_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve a signal by ID."""
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    sig = result.scalar_one_or_none()
    if sig is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found.")
    return _enrich_signal(sig)


@router.get("/", response_model=SignalListResponse)
async def list_signals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of signals (newest first)."""
    offset = (page - 1) * page_size

    count_result = await db.execute(select(func.count()).select_from(Signal))
    total = count_result.scalar_one()

    result = await db.execute(
        select(Signal)
        .order_by(Signal.generated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    signals = result.scalars().all()

    items = [
        SignalListItem(
            id=s.id,
            generated_at=s.generated_at,
            action=s.action,
            instrument=s.instrument,
            strike_a=s.strike_a,
            strike_b=s.strike_b,
            expiry=s.expiry,
            quantity=s.quantity,
            composite_score=s.composite_score,
            confidence=s.confidence,
            market_regime=s.market_regime,
        )
        for s in signals
    ]
    return SignalListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/refresh", response_model=SignalResponse)
async def refresh_signal(db: AsyncSession = Depends(get_db)):
    """Manually trigger a new signal generation run."""
    formatted = await generate_signal(db)
    return {
        "id": formatted.signal_id,
        "generated_at": formatted.generated_at,
        "action": formatted.action,
        "instrument": formatted.instrument,
        "strike_a": formatted.strike_a,
        "strike_b": formatted.strike_b,
        "expiry": formatted.expiry,
        "quantity": formatted.quantity,
        "premium_collected": formatted.premium_collected,
        "max_profit": formatted.max_profit,
        "max_loss": formatted.max_loss,
        "breakeven_a": formatted.breakeven_a,
        "breakeven_b": formatted.breakeven_b,
        "probability_of_profit": formatted.probability_of_profit,
        "expected_value": formatted.expected_value,
        "kelly_fraction": formatted.kelly_fraction,
        "composite_score": formatted.composite_score,
        "confidence": formatted.confidence,
        "iv_rank": formatted.iv_rank,
        "iv_percentile": formatted.iv_percentile,
        "market_regime": formatted.market_regime,
        "market_bias": formatted.market_bias,
        "reasoning_plain": formatted.plain_explanation,
        "reasoning_detail": formatted.detailed_reasoning,
        "greeks": formatted.greeks,
        "score_breakdown": formatted.score_breakdown,
        "alt_signal": formatted.alt_signal,
    }
