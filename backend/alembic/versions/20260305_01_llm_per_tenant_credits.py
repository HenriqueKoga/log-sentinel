"""Add enable_llm_enrichment per tenant and credits-based usage."""

import sqlalchemy as sa

from alembic import op

revision = "20260305_01_llm_credits"
down_revision = "20260304_01_add_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_plans",
        sa.Column(
            "enable_llm_enrichment", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "usage_counters",
        sa.Column("llm_enrichments", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "usage_counters",
        sa.Column("credits_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("usage_counters", "credits_used")
    op.drop_column("usage_counters", "llm_enrichments")
    op.drop_column("tenant_plans", "enable_llm_enrichment")
