"""process_email synchronously against compose Postgres (no .delay)."""

from uuid import UUID, uuid4

from app.adapters.mock_llm import MockLLMAdapter
from app.adapters.postgres_tickets import TicketRepo
from app.domain.enums import TicketStatus
from app.worker.tasks import process_email, run_process_email
from settings import settings
from sqlmodel import Session, create_engine


def _payload(*, from_email: str, message_id: str) -> dict:
    return {
        "thread_id": f"thread-{message_id}",
        "message_id": message_id,
        "from": from_email,
        "subject": "Invoice INV-2026-0001",
        "body": "Please confirm payment status.",
    }


def test_process_email_sync_persists_open_ap_ticket():
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": True, "confidence": 0.95})
    message_id = f"msg-celery-ap-{uuid4().hex[:8]}"

    result = run_process_email(
        _payload(from_email="billing@acme-supplies.com", message_id=message_id),
        llm=llm,
    )

    assert result["status"] == TicketStatus.OPEN.value
    assert result["ticket_id"] is not None
    assert len(llm.calls) == 1

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    with Session(engine) as session:
        found = TicketRepo(session).get_by_id(UUID(result["ticket_id"]))
    engine.dispose()

    assert found is not None
    assert found.message_id == message_id
    assert found.status is TicketStatus.OPEN
    assert found.is_ap is True


def test_process_email_task_quarantines_unknown_domain_without_delay():
    message_id = f"msg-celery-q-{uuid4().hex[:8]}"

    result = process_email(
        _payload(from_email="phish@evil.example", message_id=message_id)
    )

    assert result["status"] == TicketStatus.QUARANTINED.value
    assert result["ticket_id"] is not None

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    with Session(engine) as session:
        found = TicketRepo(session).get_by_id(UUID(result["ticket_id"]))
    engine.dispose()

    assert found is not None
    assert found.status is TicketStatus.QUARANTINED
