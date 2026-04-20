from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class FundamentalSnapshot(TimestampMixin, Base):
    __tablename__ = "fundamental_snapshots"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    quarter_end: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    pe_ratio: Mapped[float | None] = mapped_column(Float)
    pb_ratio: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)
    roe: Mapped[float | None] = mapped_column(Float)
    debt_to_equity: Mapped[float | None] = mapped_column(Float)
    current_ratio: Mapped[float | None] = mapped_column(Float)
    revenue_growth_yoy: Mapped[float | None] = mapped_column(Float)
    profit_growth_yoy: Mapped[float | None] = mapped_column(Float)
    next_earnings_date: Mapped[date | None] = mapped_column(Date)
    earnings_surprise_last: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual_upload", server_default="manual_upload")
