"""Triage node — MockLLMAdapter + memory store (Day 2)."""

from uuid import UUID

import pytest

from app.adapters.memory_ticket_store import InMemoryTicketStore
from app.adapters.mock_email import MockEmailAdapter
from app.adapters.mock_llm import MockLLMAdapter
from app.domain.deps import WorkflowDeps
from app.domain.enums import TicketStatus
from app.graph.nodes.ingest import make_ingest_node
from app.graph.nodes.triage import make_triage_node
from settings import Settings


def _deps(store: InMemoryTicketStore, llm: MockLLMAdapter) -> WorkflowDeps:
    return WorkflowDeps(
        settings=Settings(
            SECURITY_CHECK_ENABLED=False,
            TRIAGE_DISCARD_MIN_CONFIDENCE=0.8,
        ),
        email=MockEmailAdapter(),
        tickets=store,
        llm=llm,
    )


def _payload(message_id: str = "msg-1") -> dict:
    return {
        "thread_id": "thread-1",
        "message_id": message_id,
        "from": "billing@acme-supplies.com",
        "subject": "Invoice INV-2026-0001",
        "body": "Please confirm payment status.",
    }


async def _after_ingest(deps: WorkflowDeps, payload: dict) -> dict:
    return make_ingest_node(deps)({"raw_payload": payload})


@pytest.mark.asyncio
async def test_high_confidence_not_ap_discards():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": False, "confidence": 0.9})
    deps = _deps(store, llm)

    state = await _after_ingest(deps, _payload("msg-discard"))
    update = await make_triage_node(deps)(state)

    assert update["should_stop"] is True
    assert update["stop_reason"] == "discarded"
    ticket = store.get_by_id(UUID(update["ticket_id"]))
    assert ticket is not None
    assert ticket.status is TicketStatus.DISCARDED
    assert ticket.is_ap is False
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_is_ap_true_stays_open():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": True, "confidence": 0.95})
    deps = _deps(store, llm)

    state = await _after_ingest(deps, _payload("msg-ap"))
    update = await make_triage_node(deps)(state)

    assert update["should_stop"] is False
    ticket = store.get_by_id(UUID(update["ticket_id"]))
    assert ticket is not None
    assert ticket.status is TicketStatus.OPEN
    assert ticket.is_ap is True


@pytest.mark.asyncio
async def test_low_confidence_not_ap_stays_open():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": False, "confidence": 0.4})
    deps = _deps(store, llm)

    state = await _after_ingest(deps, _payload("msg-unsure"))
    update = await make_triage_node(deps)(state)

    assert update["should_stop"] is False
    ticket = store.get_by_id(UUID(update["ticket_id"]))
    assert ticket is not None
    assert ticket.status is TicketStatus.OPEN
    assert ticket.is_ap is False
