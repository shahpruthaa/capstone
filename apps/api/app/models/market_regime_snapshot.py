from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class MarketRegimeSnapshot(TimestampMixin, Base):
    __tablename__ = "market_regime"

    regime_date: Mapped[date] = mapped_column(Date, primary_key=True)
    regime: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    regime_confidence: Mapped[float | None] = mapped_column(Float)
    nifty_50_level: Mapped[float | None] = mapped_column(Float)
    india_vix: Mapped[float | None] = mapped_column(Float)
    advance_decline_ratio: Mapped[float | None] = mapped_column(Float)
    nifty_50d_sma: Mapped[float | None] = mapped_column(Float)
    nifty_200d_sma: Mapped[float | None] = mapped_column(Float)
    stocks_above_50d_sma_pct: Mapped[float | None] = mapped_column(Float)
    stocks_above_200d_sma_pct: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="derived_daily_bars", server_default="derived_daily_bars")
