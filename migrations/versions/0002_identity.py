"""Identity, sessions, and audit tables.

Revision ID: 0002_identity
Revises: 0001_baseline
Create Date: 2026-10-29
"""

from alembic import op

from app.db.database import Base
from app.db import models  # noqa: F401

revision = "0002_identity"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    for table in ("audit_logs", "session_tokens", "users"):
        op.drop_table(table)
