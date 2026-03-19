from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MarketSnapshotResponse(BaseModel):
    captured_at: datetime
    gld_price: Optional[float] = None
    gld_24h_change_pct: Optional[float] = None
    gld_atm_iv: Optional[float] = None
    gld_iv_rank: Optional[float] = None
    gld_iv_percentile: Optional[float] = None
    gld_hv_20d: Optional[float] = None
    vix_level: Optional[float] = None
    iv_premium_ratio: Optional[float] = None
    put_call_skew: Optional[float] = None
    market_regime: Optional[str] = None
    regime_confidence: Optional[float] = None
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    rsi_14: Optional[float] = None
    adx: Optional[float] = None
    market_session: Optional[str] = None

    class Config:
        from_attributes = True


class IVRankResponse(BaseModel):
    symbol: str
    iv_rank: float
    iv_percentile: float
    current_iv: float
    hv_20d: float
    iv_premium_ratio: float
    captured_at: datetime
