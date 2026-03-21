from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Instrument(TimestampMixin, Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("symbol", "series", name="uq_instruments_symbol_series"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    series: Mapped[str] = mapped_column(String(16), nullable=False, default="EQ")
    name: Mapped[str | None] = mapped_column(String(255))
    isin: Mapped[str | None] = mapped_column(String(32), unique=True)
    sector: Mapped[str | None] = mapped_column(String(64))
    instrument_type: Mapped[str | None] = mapped_column(String(32))
    market_cap_bucket: Mapped[str | None] = mapped_column(String(16))
    face_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    daily_bars = relationship("DailyBar", back_populates="instrument", cascade="all, delete-orphan")
    corporate_actions = relationship("CorporateAction", cascade="all, delete-orphan")
