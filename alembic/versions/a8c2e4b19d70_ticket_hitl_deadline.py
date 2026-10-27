"""ticket hitl deadline

Revision ID: a8c2e4b19d70
Revises: f3a91c2e8b40
Create Date: 2026-10-12 17:23:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8c2e4b19d70"
down_revision: str | Sequence[str] | None = "f3a91c2e8b40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("hitl_deadline", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_tickets_hitl_deadline"), "tickets", ["hitl_deadline"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tickets_hitl_deadline"), table_name="tickets")
    op.drop_column("tickets", "hitl_deadline")
