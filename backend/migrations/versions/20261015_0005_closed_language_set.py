"""map station languages onto the closed language set

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-15 10:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.catalog_normalize import normalize_language

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    raw_values = conn.execute(
        sa.text("SELECT DISTINCT language FROM stations WHERE language IS NOT NULL")
    ).scalars()
    for raw in list(raw_values):
        canonical = normalize_language(raw)
        if canonical != raw:
            conn.execute(
                sa.text("UPDATE stations SET language = :canonical WHERE language = :raw"),
                {"canonical": canonical, "raw": raw},
            )


def downgrade() -> None:
    pass
