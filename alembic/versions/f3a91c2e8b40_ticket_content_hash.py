"""ticket content hash

Revision ID: f3a91c2e8b40
Revises: 88673197cd63
Create Date: 2026-10-12 16:45:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a91c2e8b40"
down_revision: str | Sequence[str] | None = "88673197cd63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("content_hash", sa.String(length=16), nullable=True),
    )
    op.create_index(op.f("ix_tickets_content_hash"), "tickets", ["content_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tickets_content_hash"), table_name="tickets")
    op.drop_column("tickets", "content_hash")
