"""Ingest node — memory store + mock email (Day 2)."""

from uuid import UUID

from app.adapters.memory_ticket_store import InMemoryTicketStore
from app.domain.enums import TicketStatus
from app.graph.nodes.ingest import make_ingest_node
from tests.helpers import make_test_deps


def _deps(store: InMemoryTicketStore | None = None):
    return make_test_deps(tickets=store or InMemoryTicketStore())


def _payload(**overrides) -> dict:
    body = {
        "thread_id": "thread-1",
        "message_id": "msg-1",
        "from": "billing@acme-supplies.com",
        "subject": "Invoice INV-2026-0001",
        "body": "Please confirm payment status.",
    }
    body.update(overrides)
    return body


def test_valid_payload_saves_open_ticket():
    store = InMemoryTicketStore()
    ingest = make_ingest_node(_deps(store))

    update = ingest({"raw_payload": _payload()})

    assert update["should_stop"] is False
    ticket = store.get_by_message_id("msg-1")
    assert ticket is not None
    assert ticket.status is TicketStatus.OPEN
    assert ticket.sender_email == "billing@acme-supplies.com"
    assert UUID(update["ticket_id"]) == ticket.id


def test_duplicate_message_id_does_not_create_second_ticket():
    store = InMemoryTicketStore()
    ingest = make_ingest_node(_deps(store))

    first = ingest({"raw_payload": _payload()})
    second = ingest({"raw_payload": _payload(subject="Retry")})

    assert first["should_stop"] is False
    assert second["should_stop"] is True
    assert second["stop_reason"] == "duplicate"
    assert second["ticket_id"] == first["ticket_id"]
    assert len(store._by_id) == 1
    assert store.get_by_message_id("msg-1").subject == "Invoice INV-2026-0001"


def test_missing_thread_id_stops_without_ticket():
    store = InMemoryTicketStore()
    ingest = make_ingest_node(_deps(store))

    update = ingest({"raw_payload": _payload(thread_id=None)})

    assert update["should_stop"] is True
    assert update["ticket_id"] is None
    assert update["stop_reason"] == "missing_ids"
    assert store.get_by_message_id("msg-1") is None
