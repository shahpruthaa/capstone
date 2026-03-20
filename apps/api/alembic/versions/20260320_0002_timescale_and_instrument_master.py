"""timescale and instrument master enrichment

Revision ID: 20260320_0002
Revises: 20260320_0001
Create Date: 2026-03-20 18:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260320_0002"
down_revision = "20260320_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instruments", sa.Column("instrument_type", sa.String(length=32), nullable=True))
    op.add_column("instruments", sa.Column("market_cap_bucket", sa.String(length=16), nullable=True))

    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.drop_constraint("daily_bars_pkey", "daily_bars", type_="primary")
    op.create_primary_key("daily_bars_pkey", "daily_bars", ["id", "trade_date"])
    op.execute(
        """
        SELECT create_hypertable(
            'daily_bars',
            'trade_date',
            if_not_exists => TRUE,
            migrate_data => TRUE,
            chunk_time_interval => INTERVAL '30 days'
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_daily_bars_instrument_trade_date ON daily_bars (instrument_id, trade_date DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_daily_bars_instrument_trade_date")
    op.drop_constraint("daily_bars_pkey", "daily_bars", type_="primary")
    op.create_primary_key("daily_bars_pkey", "daily_bars", ["id"])
    op.drop_column("instruments", "market_cap_bucket")
    op.drop_column("instruments", "instrument_type")
