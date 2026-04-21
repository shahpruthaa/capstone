from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class InstitutionalFlow(TimestampMixin, Base):
    __tablename__ = "institutional_flows"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    flow_date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    fii_net_value: Mapped[float | None] = mapped_column(Float)
    dii_net_value: Mapped[float | None] = mapped_column(Float)
    delivery_pct: Mapped[float | None] = mapped_column(Float)
    bulk_deal_count: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual_upload", server_default="manual_upload")
