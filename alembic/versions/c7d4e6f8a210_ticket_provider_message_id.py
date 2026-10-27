"""ticket provider message id

Revision ID: c7d4e6f8a210
Revises: a8c2e4b19d70
Create Date: 2026-10-14 13:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d4e6f8a210"
down_revision: str | Sequence[str] | None = "a8c2e4b19d70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("provider_message_id", sa.String(), nullable=True),
    )
    op.create_index(
        op.f("ix_tickets_provider_message_id"),
        "tickets",
        ["provider_message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tickets_provider_message_id"), table_name="tickets")
    op.drop_column("tickets", "provider_message_id")
