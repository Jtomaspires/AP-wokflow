"""Day 3 ports/adapters — memory + fixtures + Postgres audit."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Session, create_engine

from app.adapters.memory_audit_store import InMemoryAuditStore
from app.adapters.memory_draft_store import InMemoryDraftStore
from app.adapters.mock_sap import MockSAPAdapter
from app.adapters.mock_sender_directory import MockSenderDirectory
from app.adapters.postgres_repos import AuditRepo
from app.adapters.postgres_tickets import TicketRepo
from app.domain.enums import (
    AuditAction,
    DraftTarget,
    Intent,
    InvoiceStage,
    TicketStatus,
)
from app.domain.models import AuditEntry, ResponseDraft, Ticket
from settings import settings


def test_mock_sap_loads_fixtures():
    sap = MockSAPAdapter()
    approval = sap.get_approval_invoices()
    posted = sap.get_posted_invoices()
    assert approval
    assert approval[0].stage is InvoiceStage.IN_APPROVAL
    assert posted
    assert sap.get_clearing_for_invoice("INV-2026-0002") is not None
    assert sap.get_payment_for_invoice("INV-2026-0002") is not None


def test_mock_sender_directory_email_and_rule():
    directory = MockSenderDirectory()
    sender = directory.get_by_email("billing@acme-supplies.com")
    assert sender is not None
    assert sender.company == "ACME Supplies"
    assert directory.get_by_domain("acme-supplies.com")
    rule = directory.get_routing_rule(email="billing@acme-supplies.com")
    assert rule is not None
    assert rule.operator_id == "op_joao"


def test_memory_audit_and_drafts():
    ticket_id = uuid4()
    audit = InMemoryAuditStore()
    entry = AuditEntry(ticket_id=ticket_id, node="ingest", action=AuditAction.INGEST)
    audit.append(entry)
    assert audit.get_by_ticket_id(ticket_id)[0].id == entry.id

    drafts = InMemoryDraftStore()
    draft = ResponseDraft(
        ticket_id=ticket_id,
        target=DraftTarget.SENDER,
        to_email="a@b.com",
        generated_text="hi",
    )
    drafts.save(draft)
    assert drafts.get_by_ticket_id(ticket_id)[0].id == draft.id


def test_postgres_ticket_extra_fields_and_audit():
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    suffix = uuid4().hex[:8]
    ticket = Ticket(
        thread_id=f"thread-d3-{suffix}",
        message_id=f"msg-d3-{suffix}",
        sender_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Hello",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
        status=TicketStatus.OPEN,
        intent=Intent.PAYMENT_STATUS,
        language="en",
        assigned_operator_id="op_joao",
        confidence=0.88,
        is_thread_continuation=False,
    )
    with Session(engine) as session:
        tickets = TicketRepo(session)
        saved = tickets.save_ticket(ticket)
        found = tickets.get_by_id(saved.id)
        listed = tickets.list_by_thread_id(ticket.thread_id)
        counts = tickets.count_by_status()
        audit = AuditRepo(session)
        entry = AuditEntry(
            ticket_id=saved.id,
            node="ingest",
            action=AuditAction.INGEST,
            metadata={"reason": "ok"},
        )
        audit.append(entry)
        rows = audit.get_by_ticket_id(saved.id)
    engine.dispose()

    assert found is not None
    assert found.intent is Intent.PAYMENT_STATUS
    assert found.language == "en"
    assert found.assigned_operator_id == "op_joao"
    assert listed[0].id == saved.id
    assert counts[TicketStatus.OPEN.value] >= 1
    assert len(rows) == 1
    assert rows[0].metadata["reason"] == "ok"
