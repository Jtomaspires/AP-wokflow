"""HITL service: approve sends, escalate does not."""

import json
import urllib.error
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.adapters.memory_reviews import InMemoryReviewStore
from app.adapters.memory_ticket_store import InMemoryTicketStore
from app.api.hitl import HitlConflictError, HitlService
from app.domain.enums import DraftTarget, HumanReviewAction, InvoiceStage, TicketStatus
from app.domain.models import Invoice, ResponseDraft, Ticket
from app.graph.nodes.hitl import make_hitl_node
from settings import Settings
from tests.helpers import make_test_deps


def _awaiting_ticket() -> Ticket:
    return Ticket(
        thread_id="th-hitl",
        message_id=f"msg-{uuid4().hex[:8]}",
        sender_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Pay",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
        status=TicketStatus.AWAITING_HUMAN,
    )


def test_approve_resolves_and_records_review():
    deps = make_test_deps()
    ticket = _awaiting_ticket()
    deps.tickets.save_ticket(ticket)
    deps.drafts.save(
        ResponseDraft(
            ticket_id=ticket.id,
            target=DraftTarget.SENDER,
            to_email=ticket.sender_email,
            generated_text="Hello",
        )
    )
    reviews = InMemoryReviewStore()
    result = HitlService(deps, reviews).approve(ticket.id, operator_id="op_joao")
    saved = deps.tickets.get_by_id(ticket.id)
    assert saved.status is TicketStatus.RESOLVED
    assert result["stop_reason"] == "sent"
    assert reviews.get_by_ticket_id(ticket.id)[0].action is HumanReviewAction.APPROVE


def test_approve_without_draft_conflicts():
    deps = make_test_deps()
    ticket = _awaiting_ticket()
    deps.tickets.save_ticket(ticket)
    with pytest.raises(HitlConflictError):
        HitlService(deps, InMemoryReviewStore()).approve(ticket.id, operator_id="op_joao")


def test_escalate_without_draft_ok():
    deps = make_test_deps()
    ticket = _awaiting_ticket()
    deps.tickets.save_ticket(ticket)
    result = HitlService(deps, InMemoryReviewStore()).escalate(ticket.id, operator_id="op_joao")
    saved = deps.tickets.get_by_id(ticket.id)
    assert saved.status is TicketStatus.ESCALATED
    assert result["status"] == "escalated"


def test_hitl_sets_deadline_from_invoice_due_date():
    deps = make_test_deps()
    ticket = _awaiting_ticket()
    deps.tickets.save_ticket(ticket)
    invoice = Invoice(
        invoice_ref="INV-1",
        supplier_name="ACME",
        amount=Decimal(10),
        stage=InvoiceStage.IN_APPROVAL,
        due_date=date(2026, 1, 1),
    )
    make_hitl_node(deps)(
        {
            "ticket_id": str(ticket.id),
            "invoice_dump": invoice.model_dump(mode="json"),
        }
    )
    saved = deps.tickets.get_by_id(ticket.id)
    assert saved is not None
    assert saved.hitl_deadline == datetime(2026, 1, 1, tzinfo=UTC)


def test_hitl_sets_default_deadline_when_no_invoice():
    deps = make_test_deps()
    ticket = _awaiting_ticket()
    deps.tickets.save_ticket(ticket)
    before = datetime.now(UTC)
    make_hitl_node(deps)({"ticket_id": str(ticket.id)})
    after = datetime.now(UTC)
    saved = deps.tickets.get_by_id(ticket.id)
    assert saved is not None
    assert saved.hitl_deadline is not None
    assert before + timedelta(hours=24) <= saved.hitl_deadline <= after + timedelta(hours=24)


def test_count_hitl_overdue_returns_correct_count():
    store = InMemoryTicketStore()
    past = datetime(2020, 1, 1, tzinfo=UTC)
    future = datetime(2099, 1, 1, tzinfo=UTC)

    def save(status: TicketStatus, deadline: datetime | None) -> None:
        store.save_ticket(
            Ticket(
                thread_id="th-count",
                message_id=f"msg-{uuid4().hex[:8]}",
                sender_email="billing@acme-supplies.com",
                subject="Invoice",
                body="Pay",
                received_at=datetime(2026, 8, 21, tzinfo=UTC),
                status=status,
                hitl_deadline=deadline,
            )
        )

    save(TicketStatus.AWAITING_HUMAN, past)
    save(TicketStatus.AWAITING_HUMAN, future)
    save(TicketStatus.RESOLVED, past)
    assert store.count_hitl_overdue() == 1


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def _draft(ticket: Ticket, *, to_email: str, generated_text: str) -> ResponseDraft:
    return ResponseDraft(
        ticket_id=ticket.id,
        target=DraftTarget.SENDER,
        to_email=to_email,
        generated_text=generated_text,
    )


def test_approve_flag_off_resolves_without_http(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("urlopen should not be called")

    monkeypatch.setattr("urllib.request.urlopen", fail_if_called)
    deps = make_test_deps(settings=Settings(NYLAS_SEND_ENABLED=False))
    ticket = _awaiting_ticket()
    deps.tickets.save_ticket(ticket)
    deps.drafts.save(_draft(ticket, to_email="ap-owner@company.com", generated_text="Hello"))
    result = HitlService(deps, InMemoryReviewStore()).approve(ticket.id, operator_id="op_joao")
    assert result["stop_reason"] == "sent"
    assert deps.tickets.get_by_id(ticket.id).status is TicketStatus.RESOLVED


def test_approve_sends_draft_text_to_nylas_grant(monkeypatch):
    captured: list = []

    def fake_urlopen(request, timeout=10):
        captured.append(request)
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    deps = make_test_deps(
        settings=Settings(
            NYLAS_SEND_ENABLED=True,
            NYLAS_API_KEY="test-key",
            NYLAS_GRANT_ID="grant-1",
            NYLAS_API_URI="https://api.us.nylas.com",
        )
    )
    edited = _awaiting_ticket()
    edited.subject = "Invoice question"
    edited.provider_message_id = "nylas-message-1"
    deps.tickets.save_ticket(edited)
    deps.drafts.save(_draft(edited, to_email="ap-owner@company.com", generated_text="Generated"))
    HitlService(deps, InMemoryReviewStore()).approve(
        edited.id, operator_id="op_joao", final_text="Edited body"
    )
    payload = json.loads(captured[-1].data)
    assert payload["to"][0]["email"] == "ap-owner@company.com"
    assert payload["body"] == "Edited body"
    assert payload["subject"] == "Re: Invoice question"
    assert payload["reply_to_message_id"] == edited.provider_message_id
    assert captured[-1].full_url.endswith("/v3/grants/grant-1/messages/send")
    assert deps.tickets.get_by_id(edited.id).status is TicketStatus.RESOLVED

    plain = _awaiting_ticket()
    plain.subject = "Re: Already"
    deps.tickets.save_ticket(plain)
    deps.drafts.save(_draft(plain, to_email="invoicing@company.com", generated_text="Only generated"))
    HitlService(deps, InMemoryReviewStore()).approve(plain.id, operator_id="op_joao")
    payload = json.loads(captured[-1].data)
    assert payload["to"][0]["email"] == "invoicing@company.com"
    assert payload["body"] == "Only generated"
    assert payload["subject"] == "Re: Already"
    assert "reply_to_message_id" not in payload


def test_approve_http_failure_leaves_ticket_awaiting(monkeypatch):
    def fake_urlopen(request, timeout=10):
        raise urllib.error.HTTPError(request.full_url, 502, "bad gateway", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    deps = make_test_deps(
        settings=Settings(
            NYLAS_SEND_ENABLED=True,
            NYLAS_API_KEY="test-key",
            NYLAS_GRANT_ID="grant-1",
        )
    )
    ticket = _awaiting_ticket()
    deps.tickets.save_ticket(ticket)
    deps.drafts.save(_draft(ticket, to_email="ap-owner@company.com", generated_text="Hello"))
    result = HitlService(deps, InMemoryReviewStore()).approve(ticket.id, operator_id="op_joao")
    assert result["stop_reason"] == "send_failed"
    assert deps.tickets.get_by_id(ticket.id).status is TicketStatus.AWAITING_HUMAN
    send_audit = deps.audit.get_by_ticket_id(ticket.id)[-1]
    assert send_audit.metadata["status_code"] == 502
