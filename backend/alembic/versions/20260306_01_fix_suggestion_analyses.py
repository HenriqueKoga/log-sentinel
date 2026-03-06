"""Add fix_suggestion_analyses table to persist AI-analyzed fix suggestions."""

import sqlalchemy as sa

from alembic import op

revision = "20260306_01_fix_sugg_analyses"
down_revision = "20260305_01_llm_credits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fix_suggestion_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("probable_cause", sa.Text(), nullable=False),
        sa.Column("suggested_fix", sa.Text(), nullable=False),
        sa.Column("code_snippet", sa.Text(), nullable=True),
        sa.Column("language", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fix_suggestion_analyses_tenant_id",
        "fix_suggestion_analyses",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_fix_suggestion_analyses_project_id",
        "fix_suggestion_analyses",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_fix_suggestion_analyses_fingerprint",
        "fix_suggestion_analyses",
        ["fingerprint"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_fix_suggestion_analysis_tenant_project_fingerprint",
        "fix_suggestion_analyses",
        ["tenant_id", "project_id", "fingerprint"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_fix_suggestion_analysis_tenant_project_fingerprint",
        "fix_suggestion_analyses",
        type_="unique",
    )
    op.drop_index("ix_fix_suggestion_analyses_fingerprint", table_name="fix_suggestion_analyses")
    op.drop_index("ix_fix_suggestion_analyses_project_id", table_name="fix_suggestion_analyses")
    op.drop_index("ix_fix_suggestion_analyses_tenant_id", table_name="fix_suggestion_analyses")
    op.drop_table("fix_suggestion_analyses")
