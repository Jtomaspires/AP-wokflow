"""Thread node — new vs continuation vs escalated."""

from datetime import UTC, datetime
from uuid import UUID

from app.adapters.memory_ticket_store import InMemoryTicketStore
from app.domain.enums import TicketStatus
from app.domain.models import Ticket
from app.graph.nodes.ingest import make_ingest_node
from app.graph.nodes.thread import _truncate_history, make_thread_node
from tests.helpers import make_test_deps


def _ticket(*, thread_id: str, message_id: str, status: TicketStatus) -> Ticket:
    return Ticket(
        thread_id=thread_id,
        message_id=message_id,
        sender_email="billing@acme-supplies.com",
        subject="Old",
        body="Previous",
        received_at=datetime(2026, 8, 1, tzinfo=UTC),
        status=status,
    )


def test_new_thread_routes_to_triage():
    store = InMemoryTicketStore()
    deps = make_test_deps(tickets=store)
    after = make_ingest_node(deps)(
        {
            "raw_payload": {
                "thread_id": "th-new",
                "message_id": "m1",
                "from": "billing@acme-supplies.com",
                "subject": "Invoice",
                "body": "Hi",
            }
        }
    )
    update = make_thread_node(deps)(after)
    assert update["route"] == "triage"
    assert update["is_thread_continuation"] is False
    assert update["should_stop"] is False


def test_open_thread_is_continuation_to_resolution():
    store = InMemoryTicketStore()
    store.save_ticket(_ticket(thread_id="th-c", message_id="old", status=TicketStatus.OPEN))
    deps = make_test_deps(tickets=store)
    after = make_ingest_node(deps)(
        {
            "raw_payload": {
                "thread_id": "th-c",
                "message_id": "new",
                "from": "billing@acme-supplies.com",
                "subject": "Follow up",
                "body": "Still unpaid",
            }
        }
    )
    update = make_thread_node(deps)(after)
    assert update["route"] == "resolution"
    assert update["is_thread_continuation"] is True
    prior = store.get_by_id(UUID(update["ticket_id"]))
    assert prior is not None
    assert prior.message_id == "old"
    assert "Still unpaid" in prior.body


def test_escalated_thread_stops():
    store = InMemoryTicketStore()
    store.save_ticket(
        _ticket(thread_id="th-e", message_id="esc", status=TicketStatus.ESCALATED)
    )
    deps = make_test_deps(tickets=store)
    after = make_ingest_node(deps)(
        {
            "raw_payload": {
                "thread_id": "th-e",
                "message_id": "new-e",
                "from": "billing@acme-supplies.com",
                "subject": "Ping",
                "body": "Hello again",
            }
        }
    )
    update = make_thread_node(deps)(after)
    assert update["should_stop"] is True
    assert update["stop_reason"] == "escalated_thread"


_MARKER = "[...earlier messages truncated...]"
_SEP = "\n\n---\n\n"


def test_truncate_history_leaves_short_body_unchanged():
    body = "Previous\n\n---\n\nStill unpaid"
    result = _truncate_history(body, 2000)
    assert result == body
    assert not result.startswith(_MARKER)


def test_truncate_history_keeps_last_chars_without_separator():
    body = ("x" * 2500) + "latest message"
    result = _truncate_history(body, 2000)
    assert result.startswith(f"{_MARKER}{_SEP}")
    assert result[len(_MARKER) + len(_SEP) :] == body[-2000:]
    assert result.endswith("latest message")


def test_truncate_history_starts_after_separator_in_window():
    body = ("a" * 3000) + "DROPME" + ("b" * 50) + _SEP + "latest message"
    result = _truncate_history(body, 2000)
    assert result == f"{_MARKER}{_SEP}latest message"
    assert "DROPME" not in result
    assert "aaa" not in result
