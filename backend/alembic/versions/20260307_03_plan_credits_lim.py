"""Add monthly_credits_limit to tenant_plans."""

import sqlalchemy as sa

from alembic import op

revision = "20260307_03_plan_credits_lim"
down_revision = "20260307_02_llm_usage_refactor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_plans",
        sa.Column(
            "monthly_credits_limit",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1000"),
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant_plans", "monthly_credits_limit")
