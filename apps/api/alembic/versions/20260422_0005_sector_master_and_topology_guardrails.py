"""sector master backfill and strict sector guardrails

Revision ID: 20260422_0005
Revises: 20260416_0004
Create Date: 2026-04-22 23:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260422_0005"
down_revision = "20260416_0004"
branch_labels = None
depends_on = None


SYMBOL_SECTOR_UPDATES: list[tuple[str, str]] = [
    ("ABB", "Infra"),
    ("ADANIENT", "Energy"),
    ("ADANIGREEN", "Energy"),
    ("ADANIPORTS", "Infra"),
    ("AMBUJACEM", "Cement"),
    ("APOLLOHOSP", "Pharma"),
    ("ASIANPAINT", "Chemicals"),
    ("AUROPHARMA", "Pharma"),
    ("AXISBANK", "Banking"),
    ("BAJAJ-AUTO", "Auto"),
    ("BAJAJFINSV", "Finance"),
    ("BAJFINANCE", "Finance"),
    ("BEL", "Infra"),
    ("BHARTIARTL", "Telecom"),
    ("BHEL", "Infra"),
    ("BIOCON", "Pharma"),
    ("BPCL", "Energy"),
    ("BRITANNIA", "FMCG"),
    ("CHOLAFIN", "Finance"),
    ("CIPLA", "Pharma"),
    ("COALINDIA", "Metals"),
    ("COFORGE", "IT"),
    ("DABUR", "FMCG"),
    ("DEEPAKNITRITE", "Chemicals"),
    ("DELHIVERY", "Logistics"),
    ("DIVISLAB", "Pharma"),
    ("DIXON", "Consumer Durables"),
    ("DLF", "Real Estate"),
    ("DRREDDY", "Pharma"),
    ("EICHERMOT", "Auto"),
    ("ETERNAL", "Tech/Internet"),
    ("FEDERALBNK", "Banking"),
    ("GODREJCP", "FMCG"),
    ("GODREJPROP", "Real Estate"),
    ("GOLDBEES", "Gold"),
    ("GRASIM", "Cement"),
    ("HAVELLS", "Consumer Durables"),
    ("HCLTECH", "IT"),
    ("HDFCBANK", "Banking"),
    ("HDFCLIFE", "Insurance"),
    ("HEROMOTOCO", "Auto"),
    ("HINDALCO", "Metals"),
    ("HINDUNILVR", "FMCG"),
    ("ICICIBANK", "Banking"),
    ("ICICIGI", "Insurance"),
    ("IDFCFIRSTB", "Banking"),
    ("INDUSINDBK", "Banking"),
    ("INDUSTOWER", "Telecom"),
    ("INFY", "IT"),
    ("IRCTC", "Tourism"),
    ("IRFC", "Infra"),
    ("ITC", "FMCG"),
    ("JIOFIN", "Finance"),
    ("JSWSTEEL", "Metals"),
    ("JUNIORBEES", "Index"),
    ("KOTAKBANK", "Banking"),
    ("KPITTECH", "IT"),
    ("LIQUIDBEES", "Liquid"),
    ("LT", "Infra"),
    ("LTIM", "IT"),
    ("M&M", "Auto"),
    ("MARICO", "FMCG"),
    ("MARUTI", "Auto"),
    ("MUTHOOTFIN", "Finance"),
    ("NESTLEIND", "FMCG"),
    ("NIFTYBEES", "Index"),
    ("NMDC", "Metals"),
    ("NTPC", "Energy"),
    ("NYKAA", "Tech/Internet"),
    ("ONGC", "Energy"),
    ("PAYTM", "Tech/Internet"),
    ("PERSISTENT", "IT"),
    ("PIDILITIND", "Chemicals"),
    ("POLYCAB", "Consumer Durables"),
    ("POWERGRID", "Energy"),
    ("PRESTIGE", "Real Estate"),
    ("RELIANCE", "Energy"),
    ("SBILIFE", "Insurance"),
    ("SBIN", "Banking"),
    ("SHREECEM", "Cement"),
    ("SHRIRAMFIN", "Finance"),
    ("SIEMENS", "Infra"),
    ("SILVERBEES", "Silver"),
    ("SRF", "Chemicals"),
    ("SUNPHARMA", "Pharma"),
    ("TATACONSUM", "FMCG"),
    ("TATAMOTORS", "Auto"),
    ("TATAPOWER", "Energy"),
    ("TATASTEEL", "Metals"),
    ("TCS", "IT"),
    ("TECHM", "IT"),
    ("TITAN", "Consumer Durables"),
    ("TRENT", "Consumer Durables"),
    ("TVSMOTOR", "Auto"),
    ("ULTRACEMCO", "Cement"),
    ("VEDL", "Metals"),
    ("VOLTAS", "Consumer Durables"),
    ("WIPRO", "IT"),
    ("ZOMATO", "Tech/Internet"),
]

ALLOWED_SECTORS: list[str] = [
    "IT",
    "Banking",
    "Finance",
    "FMCG",
    "Consumer Staples",
    "Energy",
    "Pharma",
    "Auto",
    "Metals",
    "Consumer Durables",
    "Infra",
    "Telecom",
    "Cement",
    "Insurance",
    "Real Estate",
    "Chemicals",
    "Tech/Internet",
    "Logistics",
    "Tourism",
    "Gold",
    "Liquid",
    "Index",
    "Silver",
    "Unknown",
]


def _allowed_sector_sql() -> str:
    quoted = ", ".join(f"'{sector}'" for sector in ALLOWED_SECTORS)
    return f"sector IN ({quoted})"


def upgrade() -> None:
    conn = op.get_bind()

    for symbol, sector in SYMBOL_SECTOR_UPDATES:
        conn.execute(
            sa.text(
                """
                UPDATE instruments
                SET sector = :sector,
                    updated_at = NOW()
                WHERE UPPER(symbol) = :symbol
                """
            ),
            {"symbol": symbol.upper(), "sector": sector},
        )

    conn.execute(
        sa.text(
            """
            UPDATE instruments
            SET sector = 'Unknown',
                updated_at = NOW()
            WHERE sector IS NULL OR BTRIM(sector) = ''
            """
        )
    )

    conn.execute(
        sa.text(
            f"""
            UPDATE instruments
            SET sector = 'Unknown',
                updated_at = NOW()
            WHERE NOT ({_allowed_sector_sql()})
            """
        )
    )

    op.alter_column(
        "instruments",
        "sector",
        existing_type=sa.String(length=64),
        nullable=False,
        server_default=sa.text("'Unknown'"),
    )

    op.create_check_constraint(
        "ck_instruments_sector_allowed",
        "instruments",
        _allowed_sector_sql(),
    )


def downgrade() -> None:
    op.drop_constraint("ck_instruments_sector_allowed", "instruments", type_="check")

    op.alter_column(
        "instruments",
        "sector",
        existing_type=sa.String(length=64),
        nullable=True,
        server_default=None,
    )
