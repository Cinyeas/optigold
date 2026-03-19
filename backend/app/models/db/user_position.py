from datetime import datetime, date
from typing import Optional
from sqlalchemy import Float, Integer, String, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base


class UserPosition(Base):
    __tablename__ = "user_position"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[Optional[str]] = mapped_column(String(30), ForeignKey("signal.id"))
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    instrument: Mapped[Optional[str]] = mapped_column(String(10))
    strategy: Mapped[Optional[str]] = mapped_column(String(30))
    strike_a: Mapped[Optional[float]] = mapped_column(Float)
    strike_b: Mapped[Optional[float]] = mapped_column(Float)
    expiry: Mapped[Optional[date]] = mapped_column(Date)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    entry_price: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="open")
    close_price: Mapped[Optional[float]] = mapped_column(Float)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    realized_pnl: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    close_reason: Mapped[Optional[str]] = mapped_column(String(20))
    # Values: profit_target | stop_loss | manual | expiry | 21dte
    actual_entry_price: Mapped[Optional[float]] = mapped_column(Float)
    entry_deviation_pct: Mapped[Optional[float]] = mapped_column(Float)
    # entry_deviation_pct = (actual_entry_price - entry_price) / entry_price × 100
