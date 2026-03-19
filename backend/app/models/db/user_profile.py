from datetime import datetime
from sqlalchemy import Boolean, Float, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base


class UserProfile(Base):
    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    capital: Mapped[float] = mapped_column(Float, nullable=False, default=50000.0)
    max_loss_per_trade: Mapped[float] = mapped_column(Float, default=2500.0)
    accepts_options: Mapped[bool] = mapped_column(Boolean, default=True)
    accepts_margin: Mapped[bool] = mapped_column(Boolean, default=False)
    accepts_unlimited_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    accepts_multi_leg: Mapped[bool] = mapped_column(Boolean, default=False)
    time_horizon: Mapped[str] = mapped_column(String(20), default="monthly")
    experience_level: Mapped[str] = mapped_column(String(20), default="beginner")
    risk_multiplier: Mapped[float] = mapped_column(Float, default=0.5)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
