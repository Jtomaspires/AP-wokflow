"""Test Gate 3 — TicketRepo against the compose Postgres database."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Session, create_engine

from app.adapters.postgres_tickets import TicketRepo
from app.domain.enums import TicketStatus
from app.domain.models import Ticket
from settings import settings


def _ticket() -> Ticket:
    suffix = uuid4().hex[:8]
    return Ticket(
        thread_id=f"thread-gate3-{suffix}",
        message_id=f"msg-gate3-{suffix}",
        sender_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Please confirm payment status.",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
        status=TicketStatus.OPEN,
    )


def test_ticket_repo_save_and_get_by_id():
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    ticket = _ticket()
    with Session(engine) as session:
        repo = TicketRepo(session)
        saved = repo.save_ticket(ticket)
        found = repo.get_by_id(saved.id)
        missing = repo.get_by_id(uuid4())

    engine.dispose()

    assert found is not None
    assert found.id == saved.id
    assert found.message_id == ticket.message_id
    assert found.sender_email == ticket.sender_email
    assert found.status is TicketStatus.OPEN
    assert missing is None
