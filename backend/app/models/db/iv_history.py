from datetime import date
from sqlalchemy import Float, Integer, String, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base


class IVHistory(Base):
    __tablename__ = "iv_history"
    __table_args__ = (UniqueConstraint("symbol", "trading_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    atm_iv: Mapped[float] = mapped_column(Float, nullable=False)
