"""Compiled graph — memory store, no Celery (Day 2)."""

from uuid import UUID

import pytest

from app.adapters.memory_ticket_store import InMemoryTicketStore
from app.adapters.mock_llm import MockLLMAdapter
from app.domain.deps import WorkflowDeps
from app.domain.enums import TicketStatus
from app.graph.app import build_graph
from settings import Settings
from tests.helpers import make_test_deps


def _deps(
    store: InMemoryTicketStore,
    llm: MockLLMAdapter,
    *,
    security_enabled: bool = True,
    whitelist: str = "acme-supplies.com",
) -> WorkflowDeps:
    return make_test_deps(
        settings=Settings(
            SECURITY_CHECK_ENABLED=security_enabled,
            SENDER_DOMAIN_WHITELIST=whitelist,
            TRIAGE_DISCARD_MIN_CONFIDENCE=0.8,
        ),
        tickets=store,
        llm=llm,
    )


def _payload(*, from_email: str, message_id: str) -> dict:
    return {
        "thread_id": "thread-1",
        "message_id": message_id,
        "from": from_email,
        "subject": "Invoice INV-2026-0001",
        "body": "Please confirm payment status.",
    }


@pytest.mark.asyncio
async def test_whitelisted_ap_email_ends_open():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": True, "confidence": 0.95})
    graph = build_graph(_deps(store, llm))

    final = await graph.ainvoke(
        {"raw_payload": _payload(from_email="billing@acme-supplies.com", message_id="msg-acme")}
    )

    ticket = store.get_by_id(UUID(final["ticket_id"]))
    assert ticket is not None
    assert ticket.status is TicketStatus.OPEN
    assert ticket.is_ap is True
    assert final["should_stop"] is False
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_unknown_domain_quarantines_without_triage():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    graph = build_graph(_deps(store, llm))

    final = await graph.ainvoke(
        {"raw_payload": _payload(from_email="phish@evil.example", message_id="msg-evil")}
    )

    ticket = store.get_by_id(UUID(final["ticket_id"]))
    assert ticket is not None
    assert ticket.status is TicketStatus.QUARANTINED
    assert final["should_stop"] is True
    assert final["stop_reason"] == "quarantined"
    assert llm.calls == []


@pytest.mark.asyncio
async def test_high_confidence_not_ap_discards():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": False, "confidence": 0.9})
    graph = build_graph(_deps(store, llm))

    final = await graph.ainvoke(
        {"raw_payload": _payload(from_email="billing@acme-supplies.com", message_id="msg-spam")}
    )

    ticket = store.get_by_id(UUID(final["ticket_id"]))
    assert ticket is not None
    assert ticket.status is TicketStatus.DISCARDED
    assert ticket.is_ap is False
    assert final["should_stop"] is True
    assert final["stop_reason"] == "discarded"
    assert len(llm.calls) == 1
