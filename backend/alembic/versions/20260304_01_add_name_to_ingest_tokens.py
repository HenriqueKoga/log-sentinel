from __future__ import annotations

from alembic import op
from logs_sentinel.infrastructure.db.models import create_all_tables

revision = "20260304_01_add_tokens"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Initial schema creation using SQLAlchemy models.

    This creates all tables defined in Base.metadata, including ingest_tokens
    with the optional `name` column.
    """

    bind = op.get_bind()
    create_all_tables(bind)


def downgrade() -> None:
    # Dropping all tables is intentionally omitted; downgrade is a no-op.
    # For development environments, the database can be recreated instead.
    pass
