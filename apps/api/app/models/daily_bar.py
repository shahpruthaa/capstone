from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class DailyBar(TimestampMixin, Base):
    __tablename__ = "daily_bars"
    __table_args__ = (UniqueConstraint("instrument_id", "trade_date", name="uq_daily_bars_instrument_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False, index=True)
    open_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    total_traded_qty: Mapped[int | None] = mapped_column(BigInteger)
    total_traded_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    total_trades: Mapped[int | None] = mapped_column(BigInteger)
    deliverable_qty: Mapped[int | None] = mapped_column(BigInteger)
    deliverable_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="nse_bhavcopy")

    instrument = relationship("Instrument", back_populates="daily_bars")
