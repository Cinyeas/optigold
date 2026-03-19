from datetime import datetime, date
from typing import Optional
from sqlalchemy import Float, Integer, String, DateTime, Date, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base


class Signal(Base):
    __tablename__ = "signal"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    instrument: Mapped[Optional[str]] = mapped_column(String(10))
    strike_a: Mapped[Optional[float]] = mapped_column(Float)
    strike_b: Mapped[Optional[float]] = mapped_column(Float)
    expiry: Mapped[Optional[date]] = mapped_column(Date)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    premium_collected: Mapped[Optional[float]] = mapped_column(Float)
    max_profit: Mapped[Optional[float]] = mapped_column(Float)
    max_loss: Mapped[Optional[float]] = mapped_column(Float)
    breakeven_a: Mapped[Optional[float]] = mapped_column(Float)
    breakeven_b: Mapped[Optional[float]] = mapped_column(Float)
    probability_of_profit: Mapped[Optional[float]] = mapped_column(Float)
    expected_value: Mapped[Optional[float]] = mapped_column(Float)
    kelly_fraction: Mapped[Optional[float]] = mapped_column(Float)
    composite_score: Mapped[Optional[float]] = mapped_column(Float)
    confidence: Mapped[Optional[str]] = mapped_column(String(10))
    iv_rank: Mapped[Optional[float]] = mapped_column(Float)
    iv_percentile: Mapped[Optional[float]] = mapped_column(Float)
    market_regime: Mapped[Optional[str]] = mapped_column(String(30))
    market_bias: Mapped[Optional[str]] = mapped_column(String(20))
    reasoning_plain: Mapped[Optional[str]] = mapped_column(Text)
    reasoning_detail: Mapped[Optional[str]] = mapped_column(Text)
    greeks_json: Mapped[Optional[str]] = mapped_column(Text)
    score_breakdown_json: Mapped[Optional[str]] = mapped_column(Text)
    alt_signal_json: Mapped[Optional[str]] = mapped_column(Text)
    snapshot_id: Mapped[Optional[int]] = mapped_column(Integer)
    pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
