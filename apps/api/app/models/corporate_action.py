from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class CorporateAction(TimestampMixin, Base):
    __tablename__ = "corporate_actions"
    __table_args__ = (
        UniqueConstraint("instrument_id", "ex_date", "action_type", name="uq_corporate_actions_instrument_date_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    ratio_numerator: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    ratio_denominator: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    cash_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    description: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual_csv")

    instrument = relationship("Instrument", back_populates="corporate_actions")
