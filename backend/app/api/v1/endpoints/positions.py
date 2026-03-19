from __future__ import annotations

"""User positions CRUD endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db
from app.models.db.user_position import UserPosition
from app.models.schemas.position import PositionCreate, PositionResponse, PositionClose

router = APIRouter()


@router.get("/", response_model=list[PositionResponse])
async def list_positions(
    status: str | None = Query(None, description="Filter by status: open, closed"),
    db: AsyncSession = Depends(get_db),
):
    """List all user positions, optionally filtered by status."""
    q = select(UserPosition).order_by(UserPosition.id.desc())
    if status:
        q = q.where(UserPosition.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=PositionResponse, status_code=201)
async def create_position(
    payload: PositionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Record a new open position (user confirmed a trade)."""
    pos_data = payload.model_dump(exclude_none=True)
    # Compute entry price deviation if actual_entry_price provided
    if payload.actual_entry_price is not None and payload.entry_price:
        pos_data["entry_deviation_pct"] = round(
            (payload.actual_entry_price - payload.entry_price) / payload.entry_price * 100, 2
        )
    pos = UserPosition(
        **pos_data,
        confirmed_at=datetime.utcnow(),
        status="open",
    )
    db.add(pos)
    await db.flush()
    return pos


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(position_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve a single position by ID."""
    result = await db.execute(
        select(UserPosition).where(UserPosition.id == position_id)
    )
    pos = result.scalar_one_or_none()
    if pos is None:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found.")
    return pos


@router.put("/{position_id}/close", response_model=PositionResponse)
async def close_position(
    position_id: int,
    payload: PositionClose,
    db: AsyncSession = Depends(get_db),
):
    """Close an open position and record P&L."""
    result = await db.execute(
        select(UserPosition).where(UserPosition.id == position_id)
    )
    pos = result.scalar_one_or_none()
    if pos is None:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found.")
    if pos.status == "closed":
        raise HTTPException(status_code=400, detail="Position is already closed.")

    pos.status = "closed"
    pos.close_price = payload.close_price
    pos.closed_at = datetime.utcnow()
    if pos.entry_price and pos.quantity:
        pos.realized_pnl = round(
            (payload.close_price - pos.entry_price) * pos.quantity * 100, 2
        )
    if payload.close_reason:
        pos.close_reason = payload.close_reason
    if payload.notes:
        pos.notes = payload.notes
    await db.flush()
    return pos


@router.delete("/{position_id}", status_code=204)
async def delete_position(position_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a position record (use only for data corrections)."""
    result = await db.execute(
        select(UserPosition).where(UserPosition.id == position_id)
    )
    pos = result.scalar_one_or_none()
    if pos is None:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found.")
    await db.delete(pos)
