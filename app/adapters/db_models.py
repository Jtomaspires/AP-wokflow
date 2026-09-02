"""SQLModel tables (assistant schema, tickets plus HITL/audit/drafts)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Column, Date, ForeignKey, Numeric, Text
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TicketTable(SQLModel, table=True):
    __tablename__ = "tickets"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    thread_id: str = Field(index=True)
    message_id: str = Field(index=True, unique=True)
    sender_email: str = Field(index=True)
    subject: str
    body: str = Field(sa_column=Column(Text, nullable=False))
    received_at: datetime
    status: str = Field(index=True)
    is_ap: bool | None = None
    intent: str | None = Field(default=None, index=True)
    language: str | None = None
    assigned_operator_id: str | None = None
    confidence: float | None = None
    is_thread_continuation: bool = False
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class SenderTable(SQLModel, table=True):
    __tablename__ = "senders"

    id: str = Field(primary_key=True)
    email: str = Field(index=True)
    name: str
    company: str
    vendor_sap_id: str | None = None
    sender_type: str
    created_at: datetime = Field(default_factory=_utc_now)


class RoutingRuleTable(SQLModel, table=True):
    __tablename__ = "routing_rules"

    id: str = Field(primary_key=True)
    operator_id: str
    email: str | None = Field(default=None, index=True)
    domain: str | None = Field(default=None, index=True)


class InvoiceCacheTable(SQLModel, table=True):
    __tablename__ = "invoice_cache"

    invoice_ref: str = Field(primary_key=True)
    supplier_name: str
    amount: Decimal = Field(sa_column=Column(Numeric(18, 2), nullable=False))
    stage: str
    currency: str = "EUR"
    status: str | None = None
    sap_id: str | None = None
    company_code: str | None = None
    payment_blocking_reason: str | None = None
    approval_step: str | None = None
    due_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    approval_owner_email: str | None = None
    clearing_document: str | None = None
    payment_document: str | None = None
    payment_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    payment_proof_ref: str | None = None


class ResponseDraftTable(SQLModel, table=True):
    __tablename__ = "response_drafts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    ticket_id: UUID = Field(sa_column=Column(ForeignKey("tickets.id"), nullable=False, index=True))
    target: str
    to_email: str
    generated_text: str = Field(sa_column=Column(Text, nullable=False))
    final_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    edited_by_human: bool = False
    operator_notes: str | None = None
    attach_invoice_pdf: bool = False
    attach_payment_proof: bool = False
    created_at: datetime = Field(default_factory=_utc_now)


class AuditEntryTable(SQLModel, table=True):
    __tablename__ = "audit_entries"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    ticket_id: UUID = Field(sa_column=Column(ForeignKey("tickets.id"), nullable=False, index=True))
    node: str
    action: str
    confidence: float | None = None
    metadata_json: dict = Field(default_factory=dict, sa_column=Column("metadata", JSON, nullable=False))
    created_at: datetime = Field(default_factory=_utc_now)


class HumanReviewTable(SQLModel, table=True):
    __tablename__ = "human_reviews"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    ticket_id: UUID = Field(sa_column=Column(ForeignKey("tickets.id"), nullable=False, index=True))
    draft_id: UUID = Field(sa_column=Column(ForeignKey("response_drafts.id"), nullable=False, index=True))
    action: str
    operator_id: str
    notes: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
