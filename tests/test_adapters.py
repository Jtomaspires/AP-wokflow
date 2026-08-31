"""Test Gate 2 — mock email, mock LLM, in-memory ticket store."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.adapters.memory_ticket_store import InMemoryTicketStore
from app.adapters.mock_email import MockEmailAdapter
from app.adapters.mock_llm import MockLLMAdapter
from app.domain.enums import TicketStatus
from app.domain.models import Ticket
from app.domain.schemas import TriageOutput


def test_parse_webhook_maps_from_to_from_email():
    event = MockEmailAdapter().parse_webhook(
        {
            "thread_id": "thread-1",
            "message_id": "msg-1",
            "from": "billing@acme-supplies.com",
            "subject": "Invoice",
            "body": "Hello",
        }
    )
    assert event.from_email == "billing@acme-supplies.com"
    assert event.thread_id == "thread-1"
    assert event.message_id == "msg-1"


@pytest.mark.asyncio
async def test_mock_llm_returns_triage_output():
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": True, "confidence": 0.91})
    output = await llm.generate(
        system_prompt="triage",
        user_prompt="invoice email",
        output_schema=TriageOutput,
    )
    assert isinstance(output, TriageOutput)
    assert output.is_ap is True
    assert output.confidence == 0.91


@pytest.mark.asyncio
async def test_mock_llm_empty_queue_raises():
    llm = MockLLMAdapter()
    with pytest.raises(RuntimeError, match="no queued responses"):
        await llm.generate(
            system_prompt="triage",
            user_prompt="invoice email",
            output_schema=TriageOutput,
        )


def test_memory_store_save_and_get_by_message_id():
    store = InMemoryTicketStore()
    ticket = Ticket(
        thread_id="thread-1",
        message_id="msg-1",
        sender_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Hello",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
        status=TicketStatus.OPEN,
    )
    saved = store.save_ticket(ticket)
    assert isinstance(saved.id, UUID)
    found = store.get_by_message_id("msg-1")
    assert found is not None
    assert found.id == saved.id
    assert store.get_by_id(saved.id) == saved
    assert store.get_by_message_id("missing") is None
