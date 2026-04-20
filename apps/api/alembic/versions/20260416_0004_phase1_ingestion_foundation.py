"""phase 1 ingestion foundation

Revision ID: 20260416_0004
Revises: 20260321_0003
Create Date: 2026-04-16 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260416_0004"
down_revision = "20260321_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "options_snapshots",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("pcr_ratio", sa.Float(), nullable=True),
        sa.Column("iv_percentile", sa.Float(), nullable=True),
        sa.Column("max_pain", sa.Float(), nullable=True),
        sa.Column("call_oi_change_pct", sa.Float(), nullable=True),
        sa.Column("put_oi_change_pct", sa.Float(), nullable=True),
        sa.Column("unusual_activity", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("avg_implied_volatility", sa.Float(), nullable=True),
        sa.Column("total_call_oi", sa.Float(), nullable=True),
        sa.Column("total_put_oi", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="nse_options"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "snapshot_date"),
    )
    op.create_index("ix_options_snapshots_snapshot_date", "options_snapshots", ["snapshot_date"], unique=False)
    op.create_index("ix_options_snapshots_expiry_date", "options_snapshots", ["expiry_date"], unique=False)

    op.create_table(
        "institutional_flows",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("flow_date", sa.Date(), nullable=False),
        sa.Column("fii_net_value", sa.Float(), nullable=True),
        sa.Column("dii_net_value", sa.Float(), nullable=True),
        sa.Column("delivery_pct", sa.Float(), nullable=True),
        sa.Column("bulk_deal_count", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="manual_upload"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "flow_date"),
    )
    op.create_index("ix_institutional_flows_flow_date", "institutional_flows", ["flow_date"], unique=False)

    op.create_table(
        "fundamental_snapshots",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("quarter_end", sa.Date(), nullable=False),
        sa.Column("pe_ratio", sa.Float(), nullable=True),
        sa.Column("pb_ratio", sa.Float(), nullable=True),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("roe", sa.Float(), nullable=True),
        sa.Column("debt_to_equity", sa.Float(), nullable=True),
        sa.Column("current_ratio", sa.Float(), nullable=True),
        sa.Column("revenue_growth_yoy", sa.Float(), nullable=True),
        sa.Column("profit_growth_yoy", sa.Float(), nullable=True),
        sa.Column("next_earnings_date", sa.Date(), nullable=True),
        sa.Column("earnings_surprise_last", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="manual_upload"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "quarter_end"),
    )
    op.create_index("ix_fundamental_snapshots_quarter_end", "fundamental_snapshots", ["quarter_end"], unique=False)

    op.create_table(
        "market_regime",
        sa.Column("regime_date", sa.Date(), nullable=False),
        sa.Column("regime", sa.String(length=32), nullable=False),
        sa.Column("regime_confidence", sa.Float(), nullable=True),
        sa.Column("nifty_50_level", sa.Float(), nullable=True),
        sa.Column("india_vix", sa.Float(), nullable=True),
        sa.Column("advance_decline_ratio", sa.Float(), nullable=True),
        sa.Column("nifty_50d_sma", sa.Float(), nullable=True),
        sa.Column("nifty_200d_sma", sa.Float(), nullable=True),
        sa.Column("stocks_above_50d_sma_pct", sa.Float(), nullable=True),
        sa.Column("stocks_above_200d_sma_pct", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="derived_daily_bars"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("regime_date"),
    )
    op.create_index("ix_market_regime_regime", "market_regime", ["regime"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_market_regime_regime", table_name="market_regime")
    op.drop_table("market_regime")
    op.drop_index("ix_fundamental_snapshots_quarter_end", table_name="fundamental_snapshots")
    op.drop_table("fundamental_snapshots")
    op.drop_index("ix_institutional_flows_flow_date", table_name="institutional_flows")
    op.drop_table("institutional_flows")
    op.drop_index("ix_options_snapshots_expiry_date", table_name="options_snapshots")
    op.drop_index("ix_options_snapshots_snapshot_date", table_name="options_snapshots")
    op.drop_table("options_snapshots")
