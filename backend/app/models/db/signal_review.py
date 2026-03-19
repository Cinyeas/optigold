from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base


class SignalReview(Base):
    __tablename__ = "signal_review"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_signal_id: Mapped[Optional[str]] = mapped_column(
        String(30), ForeignKey("signal.id")
    )
    position_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("user_position.id")
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    trigger: Mapped[Optional[str]] = mapped_column(String(30))
    conclusion: Mapped[Optional[str]] = mapped_column(String(20))
    reasoning: Mapped[Optional[str]] = mapped_column(Text)
    urgency: Mapped[Optional[str]] = mapped_column(String(10))
    new_signal_id: Mapped[Optional[str]] = mapped_column(
        String(30), ForeignKey("signal.id")
    )
