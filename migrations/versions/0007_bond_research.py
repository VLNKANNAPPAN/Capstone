"""Add canonical bond securities and sovereign yield-curve points.

Revision ID: 0007_bond_research
Revises: 0006_filing_intelligence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_bond_research"
down_revision: str | None = "0006_filing_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bond_securities",
        sa.Column("isin", sa.String(length=16), primary_key=True),
        sa.Column("issuer", sa.String(length=255), nullable=False),
        sa.Column("security_name", sa.Text(), nullable=False),
        sa.Column("bond_type", sa.String(length=32), nullable=False),
        sa.Column("coupon_rate_pct", sa.Numeric(12, 6)),
        sa.Column("coupon_frequency", sa.Integer(), nullable=False),
        sa.Column("issue_date", sa.Date()),
        sa.Column("maturity_date", sa.Date(), nullable=False),
        sa.Column("face_value", sa.Numeric(24, 4), nullable=False),
        sa.Column("issue_price", sa.Numeric(24, 4)),
        sa.Column("rating", sa.String(length=64)),
        sa.Column("rating_agency", sa.String(length=255)),
        sa.Column("rating_outlook", sa.String(length=64)),
        sa.Column("secured", sa.Boolean()),
        sa.Column("seniority", sa.String(length=128)),
        sa.Column("callable", sa.Boolean(), nullable=False),
        sa.Column("puttable", sa.Boolean(), nullable=False),
        sa.Column("sector", sa.String(length=255)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bond_issuer_maturity", "bond_securities", ["issuer", "maturity_date"])
    op.create_index("ix_bond_rating_maturity", "bond_securities", ["rating", "maturity_date"])
    op.create_table(
        "yield_curve_points",
        sa.Column("source", sa.String(length=64), primary_key=True),
        sa.Column("curve_date", sa.Date(), primary_key=True),
        sa.Column("tenor_years", sa.Numeric(12, 6), primary_key=True),
        sa.Column("yield_pct", sa.Numeric(12, 6), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_yield_curve_date_tenor", "yield_curve_points", ["curve_date", "tenor_years"]
    )


def downgrade() -> None:
    op.drop_index("ix_yield_curve_date_tenor", table_name="yield_curve_points")
    op.drop_table("yield_curve_points")
    op.drop_index("ix_bond_rating_maturity", table_name="bond_securities")
    op.drop_index("ix_bond_issuer_maturity", table_name="bond_securities")
    op.drop_table("bond_securities")
