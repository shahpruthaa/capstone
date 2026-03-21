"""corporate actions table

Revision ID: 20260321_0003
Revises: 20260320_0002
Create Date: 2026-03-21 10:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260321_0003"
down_revision = "20260320_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("ratio_numerator", sa.Numeric(18, 6), nullable=True),
        sa.Column("ratio_denominator", sa.Numeric(18, 6), nullable=True),
        sa.Column("cash_amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="manual_csv"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument_id", "ex_date", "action_type", name="uq_corporate_actions_instrument_date_type"),
    )
    op.create_index("ix_corporate_actions_instrument_id", "corporate_actions", ["instrument_id"], unique=False)
    op.create_index("ix_corporate_actions_ex_date", "corporate_actions", ["ex_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_corporate_actions_ex_date", table_name="corporate_actions")
    op.drop_index("ix_corporate_actions_instrument_id", table_name="corporate_actions")
    op.drop_table("corporate_actions")
