"""initial schema

Revision ID: 20260320_0001
Revises:
Create Date: 2026-03-20 17:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260320_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("strategy_name", sa.String(length=64), nullable=False),
        sa.Column("risk_mode", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_backtest_runs_risk_mode"), "backtest_runs", ["risk_mode"], unique=False)
    op.create_index(op.f("ix_backtest_runs_status"), "backtest_runs", ["status"], unique=False)

    op.create_table(
        "generated_portfolio_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("risk_mode", sa.String(length=32), nullable=False),
        sa.Column("investment_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column("metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generated_portfolio_runs_risk_mode"), "generated_portfolio_runs", ["risk_mode"], unique=False)

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("dataset", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("records_inserted", sa.Integer(), nullable=False),
        sa.Column("records_updated", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingestion_runs_dataset"), "ingestion_runs", ["dataset"], unique=False)
    op.create_index(op.f("ix_ingestion_runs_source"), "ingestion_runs", ["source"], unique=False)
    op.create_index(op.f("ix_ingestion_runs_status"), "ingestion_runs", ["status"], unique=False)

    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("series", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("isin", sa.String(length=32), nullable=True),
        sa.Column("sector", sa.String(length=64), nullable=True),
        sa.Column("face_value", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("isin"),
        sa.UniqueConstraint("symbol", "series", name="uq_instruments_symbol_series"),
    )
    op.create_index(op.f("ix_instruments_symbol"), "instruments", ["symbol"], unique=False)

    op.create_table(
        "daily_bars",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("high_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("low_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("close_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("last_price", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("prev_close", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("total_traded_qty", sa.BigInteger(), nullable=True),
        sa.Column("total_traded_value", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("total_trades", sa.BigInteger(), nullable=True),
        sa.Column("deliverable_qty", sa.BigInteger(), nullable=True),
        sa.Column("deliverable_pct", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument_id", "trade_date", name="uq_daily_bars_instrument_date"),
    )
    op.create_index(op.f("ix_daily_bars_instrument_id"), "daily_bars", ["instrument_id"], unique=False)
    op.create_index(op.f("ix_daily_bars_trade_date"), "daily_bars", ["trade_date"], unique=False)

    op.create_table(
        "generated_portfolio_allocations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("portfolio_run_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("sector", sa.String(length=64), nullable=True),
        sa.Column("weight", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_run_id"], ["generated_portfolio_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generated_portfolio_allocations_portfolio_run_id"), "generated_portfolio_allocations", ["portfolio_run_id"], unique=False)
    op.create_index(op.f("ix_generated_portfolio_allocations_symbol"), "generated_portfolio_allocations", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_generated_portfolio_allocations_symbol"), table_name="generated_portfolio_allocations")
    op.drop_index(op.f("ix_generated_portfolio_allocations_portfolio_run_id"), table_name="generated_portfolio_allocations")
    op.drop_table("generated_portfolio_allocations")
    op.drop_index(op.f("ix_daily_bars_trade_date"), table_name="daily_bars")
    op.drop_index(op.f("ix_daily_bars_instrument_id"), table_name="daily_bars")
    op.drop_table("daily_bars")
    op.drop_index(op.f("ix_instruments_symbol"), table_name="instruments")
    op.drop_table("instruments")
    op.drop_index(op.f("ix_ingestion_runs_status"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_source"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_dataset"), table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_index(op.f("ix_generated_portfolio_runs_risk_mode"), table_name="generated_portfolio_runs")
    op.drop_table("generated_portfolio_runs")
    op.drop_index(op.f("ix_backtest_runs_status"), table_name="backtest_runs")
    op.drop_index(op.f("ix_backtest_runs_risk_mode"), table_name="backtest_runs")
    op.drop_table("backtest_runs")
