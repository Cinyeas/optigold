from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel


class PositionCreate(BaseModel):
    signal_id: Optional[str] = None
    instrument: Optional[str] = None
    strategy: Optional[str] = None
    strike_a: Optional[float] = None
    strike_b: Optional[float] = None
    expiry: Optional[date] = None
    quantity: Optional[int] = None
    entry_price: Optional[float] = None
    actual_entry_price: Optional[float] = None  # if user filled at different price
    notes: Optional[str] = None


class PositionResponse(BaseModel):
    id: int
    signal_id: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    instrument: Optional[str] = None
    strategy: Optional[str] = None
    strike_a: Optional[float] = None
    strike_b: Optional[float] = None
    expiry: Optional[date] = None
    quantity: Optional[int] = None
    entry_price: Optional[float] = None
    actual_entry_price: Optional[float] = None
    entry_deviation_pct: Optional[float] = None
    status: str
    close_price: Optional[float] = None
    closed_at: Optional[datetime] = None
    realized_pnl: Optional[float] = None
    close_reason: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class PositionClose(BaseModel):
    close_price: float
    close_reason: Optional[str] = None
    # profit_target | stop_loss | manual | expiry | 21dte
    notes: Optional[str] = None


class PositionUpdate(BaseModel):
    """Editable fields for correcting a mistaken entry."""
    entry_price: Optional[float] = None
    actual_entry_price: Optional[float] = None
    quantity: Optional[int] = None
    strike_a: Optional[float] = None
    strike_b: Optional[float] = None
    expiry: Optional[date] = None
    notes: Optional[str] = None
