from __future__ import annotations

from datetime import datetime, date
from typing import Any, Optional
from pydantic import BaseModel


class SignalListItem(BaseModel):
    id: str
    generated_at: datetime
    action: str
    instrument: Optional[str] = None
    strike_a: Optional[float] = None
    strike_b: Optional[float] = None
    expiry: Optional[date] = None
    quantity: Optional[int] = None
    composite_score: Optional[float] = None
    confidence: Optional[str] = None
    market_regime: Optional[str] = None

    class Config:
        from_attributes = True


class SignalResponse(BaseModel):
    id: str
    generated_at: datetime
    action: str
    instrument: Optional[str] = None
    strike_a: Optional[float] = None
    strike_b: Optional[float] = None
    expiry: Optional[date] = None
    quantity: Optional[int] = None
    premium_collected: Optional[float] = None
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    breakeven_a: Optional[float] = None
    breakeven_b: Optional[float] = None
    probability_of_profit: Optional[float] = None
    expected_value: Optional[float] = None
    kelly_fraction: Optional[float] = None
    composite_score: Optional[float] = None
    confidence: Optional[str] = None
    iv_rank: Optional[float] = None
    iv_percentile: Optional[float] = None
    market_regime: Optional[str] = None
    market_bias: Optional[str] = None
    reasoning_plain: Optional[str] = None
    reasoning_detail: Optional[str] = None
    greeks: Optional[Any] = None
    score_breakdown: Optional[Any] = None
    alt_signal: Optional[Any] = None
    snapshot_id: Optional[int] = None
    pushed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SignalListResponse(BaseModel):
    items: list[SignalListItem]
    total: int
    page: int
    page_size: int
