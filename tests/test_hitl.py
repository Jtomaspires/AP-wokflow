"""HITL service: approve sends, escalate does not."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.adapters.memory_reviews import InMemoryReviewStore
from app.api.hitl import HitlConflictError, HitlService
from app.domain.enums import DraftTarget, HumanReviewAction, TicketStatus
from app.domain.models import ResponseDraft, Ticket
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
