"""Test Gate 1 — domain enums and Pydantic models."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.enums import TicketStatus
from app.domain.events import IncomingEmail
from app.domain.models import Ticket


def _ticket(**overrides) -> Ticket:
    payload = {
        "thread_id": "thread-1",
        "message_id": "msg-1",
        "sender_email": "billing@acme-supplies.com",
        "subject": "Invoice INV-2026-0001",
        "body": "Please confirm payment status.",
        "received_at": datetime(2026, 8, 21, tzinfo=UTC),
    }
    payload.update(overrides)
    return Ticket.model_validate(payload)


def test_ticket_status_members():
    assert TicketStatus.OPEN.value == "open"
    assert {member.value for member in TicketStatus} == {
        "open",
        "awaiting_human",
        "awaiting_sender_reply",
        "resolved",
        "escalated",
        "quarantined",
        "discarded",
        "delegated",
    }


def test_incoming_email_requires_from_email():
    event = IncomingEmail(from_email="billing@acme-supplies.com")
    assert event.from_email == "billing@acme-supplies.com"
    assert event.thread_id is None
    assert event.message_id is None


def test_incoming_email_rejects_missing_from_email():
    with pytest.raises(ValidationError):
        IncomingEmail()


def test_ticket_validates_with_required_fields():
    ticket = _ticket()
    assert ticket.thread_id == "thread-1"
    assert ticket.status is TicketStatus.OPEN
    assert ticket.is_ap is None
    assert isinstance(ticket.id, UUID)


def test_ticket_rejects_missing_thread_id():
    with pytest.raises(ValidationError):
        Ticket(
            message_id="msg-1",
            sender_email="billing@acme-supplies.com",
            subject="Invoice",
            body="Hello",
            received_at=datetime(2026, 8, 21, tzinfo=UTC),
        )


def test_ticket_round_trip():
    ticket = _ticket()
    restored = Ticket.model_validate(ticket.model_dump())
    assert restored == ticket


def test_incoming_email_round_trip():
    event = IncomingEmail(
        thread_id="thread-1",
        message_id="msg-1",
        from_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Hello",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
    )
    restored = IncomingEmail.model_validate(event.model_dump())
    assert restored == event


def test_ticket_optional_assistant_fields_default():
    ticket = _ticket()
    assert ticket.intent is None
    assert ticket.is_thread_continuation is False
    assert ticket.assigned_operator_id is None


def test_sender_and_draft_round_trip():
    from decimal import Decimal
    from uuid import uuid4

    from app.domain.enums import (
        AuditAction,
        DraftTarget,
        Intent,
        InvoiceStage,
        SenderType,
    )
    from app.domain.models import AuditEntry, Invoice, ResponseDraft, Sender

    sender = Sender(
        id="snd-1",
        email="billing@acme-supplies.com",
        name="ACME",
        company="ACME Supplies",
        sender_type=SenderType.VENDOR,
    )
    assert Sender.model_validate(sender.model_dump()) == sender

    invoice = Invoice(
        invoice_ref="INV-1",
        supplier_name="ACME Supplies",
        amount=Decimal("10.00"),
        stage=InvoiceStage.POSTED,
    )
    assert Invoice.model_validate(invoice.model_dump()) == invoice

    ticket_id = uuid4()
    draft = ResponseDraft(
        ticket_id=ticket_id,
        target=DraftTarget.SENDER,
        to_email="billing@acme-supplies.com",
        generated_text="Hello",
    )
    assert ResponseDraft.model_validate(draft.model_dump()) == draft

    audit = AuditEntry(
        ticket_id=ticket_id,
        node="ingest",
        action=AuditAction.INGEST,
    )
    assert AuditEntry.model_validate(audit.model_dump()) == audit

    ticket = _ticket(intent=Intent.PAYMENT_STATUS, language="en")
    assert ticket.intent is Intent.PAYMENT_STATUS

