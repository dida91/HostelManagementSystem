"""enable required postgresql extensions

Revision ID: 0001_extensions
Revises:
"""
from __future__ import annotations

from alembic import op

revision = "0001_extensions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')


def downgrade() -> None:
    # Extensions are shared infrastructure; dropping them could break other
    # objects in the database, so downgrade deliberately leaves them in place.
    pass
