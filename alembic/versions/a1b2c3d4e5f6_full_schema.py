"""tickets extra columns + audit/drafts/HITL/senders (Day 3).

Revision ID: a1b2c3d4e5f6
Revises: edb81d2a0b75
Create Date: 2026-09-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "edb81d2a0b75"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("intent", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("tickets", sa.Column("language", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column(
        "tickets",
        sa.Column("assigned_operator_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column("tickets", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column(
        "tickets",
        sa.Column("is_thread_continuation", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(op.f("ix_tickets_intent"), "tickets", ["intent"], unique=False)

    op.create_table(
        "senders",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("company", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("vendor_sap_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("sender_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_senders_email"), "senders", ["email"], unique=False)

    op.create_table(
        "routing_rules",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("operator_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("domain", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_routing_rules_email"), "routing_rules", ["email"], unique=False)
    op.create_index(op.f("ix_routing_rules_domain"), "routing_rules", ["domain"], unique=False)

    op.create_table(
        "invoice_cache",
        sa.Column("invoice_ref", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("supplier_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("stage", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("sap_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("company_code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("payment_blocking_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("approval_step", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("approval_owner_email", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("clearing_document", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("payment_document", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("payment_proof_ref", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("invoice_ref"),
    )

    op.create_table(
        "response_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("target", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("to_email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("generated_text", sa.Text(), nullable=False),
        sa.Column("final_text", sa.Text(), nullable=True),
        sa.Column("edited_by_human", sa.Boolean(), nullable=False),
        sa.Column("operator_notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("attach_invoice_pdf", sa.Boolean(), nullable=False),
        sa.Column("attach_payment_proof", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_response_drafts_ticket_id"), "response_drafts", ["ticket_id"], unique=False)

    op.create_table(
        "audit_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("node", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_entries_ticket_id"), "audit_entries", ["ticket_id"], unique=False)

    op.create_table(
        "human_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("operator_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["response_drafts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_human_reviews_ticket_id"), "human_reviews", ["ticket_id"], unique=False)
    op.create_index(op.f("ix_human_reviews_draft_id"), "human_reviews", ["draft_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_human_reviews_draft_id"), table_name="human_reviews")
    op.drop_index(op.f("ix_human_reviews_ticket_id"), table_name="human_reviews")
    op.drop_table("human_reviews")
    op.drop_index(op.f("ix_audit_entries_ticket_id"), table_name="audit_entries")
    op.drop_table("audit_entries")
    op.drop_index(op.f("ix_response_drafts_ticket_id"), table_name="response_drafts")
    op.drop_table("response_drafts")
    op.drop_table("invoice_cache")
    op.drop_index(op.f("ix_routing_rules_domain"), table_name="routing_rules")
    op.drop_index(op.f("ix_routing_rules_email"), table_name="routing_rules")
    op.drop_table("routing_rules")
    op.drop_index(op.f("ix_senders_email"), table_name="senders")
    op.drop_table("senders")
    op.drop_index(op.f("ix_tickets_intent"), table_name="tickets")
    op.drop_column("tickets", "is_thread_continuation")
    op.drop_column("tickets", "confidence")
    op.drop_column("tickets", "assigned_operator_id")
    op.drop_column("tickets", "language")
    op.drop_column("tickets", "intent")
