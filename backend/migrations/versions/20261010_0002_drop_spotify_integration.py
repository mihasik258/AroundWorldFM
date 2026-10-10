"""drop spotify integration

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10 20:55:23.925095+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM auth_flows WHERE provider = 'spotify'")
    op.execute("DELETE FROM user_identities WHERE provider = 'spotify'")
    op.drop_table("oauth_credentials")
    op.drop_column("auth_flows", "code_verifier_enc")


def downgrade() -> None:
    op.add_column(
        "auth_flows", sa.Column("code_verifier_enc", sa.TEXT(), autoincrement=False, nullable=True)
    )
    op.create_table(
        "oauth_credentials",
        sa.Column("identity_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("access_token_enc", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("refresh_token_enc", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column(
            "expires_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column("scope", sa.VARCHAR(length=512), autoincrement=False, nullable=False),
        sa.Column("playlist_id", sa.VARCHAR(length=64), autoincrement=False, nullable=True),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["user_identities.id"],
            name=op.f("fk_oauth_credentials_identity_id_user_identities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("identity_id", name=op.f("pk_oauth_credentials")),
    )
