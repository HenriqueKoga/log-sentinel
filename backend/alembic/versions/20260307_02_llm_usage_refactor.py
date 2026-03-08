"""Refactor billing: remove credits_used, add llm_models, llm_usages, credit_policies."""

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "20260307_02_llm_usage_refactor"
down_revision = "20260307_01_chat_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("usage_counters", "credits_used")

    op.create_table(
        "llm_models",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("input_token_price", sa.Float(), nullable=False),
        sa.Column("output_token_price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("supports_usage_tracking", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "model_name", name="uq_llm_model_provider_name"),
    )

    op.create_table(
        "llm_usages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("project_id", sa.Integer(), nullable=True, index=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("llm_model_id", sa.Integer(), sa.ForeignKey("llm_models.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("feature_name", sa.String(64), nullable=False, index=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "credit_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("credits_per_currency_unit", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Seed default models
    now = datetime.now(tz=UTC)
    llm_models = sa.table(
        "llm_models",
        sa.column("provider", sa.String),
        sa.column("model_name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("input_token_price", sa.Float),
        sa.column("output_token_price", sa.Float),
        sa.column("currency", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("supports_usage_tracking", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        llm_models,
        [
            {
                "provider": "openai",
                "model_name": "gpt-4o-mini",
                "display_name": "GPT-4o Mini",
                "input_token_price": 0.00000015,
                "output_token_price": 0.0000006,
                "currency": "USD",
                "is_active": True,
                "supports_usage_tracking": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "provider": "openai",
                "model_name": "gpt-4o",
                "display_name": "GPT-4o",
                "input_token_price": 0.0000025,
                "output_token_price": 0.00001,
                "currency": "USD",
                "is_active": True,
                "supports_usage_tracking": True,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )

    # Seed default credit policy: 1 USD = 100 credits
    credit_policies = sa.table(
        "credit_policies",
        sa.column("name", sa.String),
        sa.column("currency", sa.String),
        sa.column("credits_per_currency_unit", sa.Float),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        credit_policies,
        [
            {
                "name": "default",
                "currency": "USD",
                "credits_per_currency_unit": 100.0,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("credit_policies")
    op.drop_table("llm_usages")
    op.drop_table("llm_models")
    op.add_column(
        "usage_counters",
        sa.Column("credits_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
