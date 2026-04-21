from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class OptionsSnapshot(TimestampMixin, Base):
    __tablename__ = "options_snapshots"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True)
    pcr_ratio: Mapped[float | None] = mapped_column(Float)
    iv_percentile: Mapped[float | None] = mapped_column(Float)
    max_pain: Mapped[float | None] = mapped_column(Float)
    call_oi_change_pct: Mapped[float | None] = mapped_column(Float)
    put_oi_change_pct: Mapped[float | None] = mapped_column(Float)
    unusual_activity: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    avg_implied_volatility: Mapped[float | None] = mapped_column(Float)
    total_call_oi: Mapped[float | None] = mapped_column(Float)
    total_put_oi: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="nse_options", server_default="nse_options")
