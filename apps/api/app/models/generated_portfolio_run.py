from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class GeneratedPortfolioRun(TimestampMixin, Base):
    __tablename__ = "generated_portfolio_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    risk_mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    investment_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    as_of_date: Mapped[date | None] = mapped_column(Date)
    metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)

    allocations = relationship("GeneratedPortfolioAllocation", back_populates="portfolio_run", cascade="all, delete-orphan")


class GeneratedPortfolioAllocation(TimestampMixin, Base):
    __tablename__ = "generated_portfolio_allocations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_run_id: Mapped[str] = mapped_column(ForeignKey("generated_portfolio_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sector: Mapped[str | None] = mapped_column(String(64))
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)

    portfolio_run = relationship("GeneratedPortfolioRun", back_populates="allocations")
