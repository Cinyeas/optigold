from datetime import datetime
from typing import Optional
from sqlalchemy import Float, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base


class MarketSnapshot(Base):
    __tablename__ = "market_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    gld_price: Mapped[Optional[float]] = mapped_column(Float)
    gld_24h_change_pct: Mapped[Optional[float]] = mapped_column(Float)
    gld_atm_iv: Mapped[Optional[float]] = mapped_column(Float)
    gld_iv_rank: Mapped[Optional[float]] = mapped_column(Float)
    gld_iv_percentile: Mapped[Optional[float]] = mapped_column(Float)
    gld_hv_20d: Mapped[Optional[float]] = mapped_column(Float)
    vix_level: Mapped[Optional[float]] = mapped_column(Float)
    iv_premium_ratio: Mapped[Optional[float]] = mapped_column(Float)
    put_call_skew: Mapped[Optional[float]] = mapped_column(Float)
    market_regime: Mapped[Optional[str]] = mapped_column(String(30))
    regime_confidence: Mapped[Optional[float]] = mapped_column(Float)
    ema20: Mapped[Optional[float]] = mapped_column(Float)
    ema50: Mapped[Optional[float]] = mapped_column(Float)
    rsi_14: Mapped[Optional[float]] = mapped_column(Float)
    adx: Mapped[Optional[float]] = mapped_column(Float)
    market_session: Mapped[Optional[str]] = mapped_column(String(20))
