"""Intent, skip_identity, delegate vs mine (Day 4)."""

from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, create_engine

from app.adapters.memory_ticket_store import InMemoryTicketStore
from app.adapters.mock_llm import MockLLMAdapter
from app.adapters.mock_sender_directory import MockSenderDirectory
from app.domain.enums import AuditAction, Intent, TicketStatus
from app.domain.models import RoutingRule, Sender
from app.adapters.postgres_repos import AuditRepo
from app.api.deps import build_workflow_deps
from app.graph.app import build_graph
from settings import Settings
from settings import settings as app_settings
from tests.helpers import make_test_deps


def _intent_payload(message_id: str) -> dict:
    return {
        "thread_id": f"thread-{message_id}",
        "message_id": message_id,
        "from": "billing@acme-supplies.com",
        "subject": "Invoice INV-2026-0001",
        "body": "Please confirm payment status.",
    }


@pytest.mark.asyncio
async def test_known_intent_goes_to_sender_and_mine():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": True, "confidence": 0.95})
    llm.enqueue(
        {
            "intent": "payment_status",
            "confidence": 0.9,
            "language": "en",
            "extracted_ref": "INV-1",
            "extracted_amount": 10.0,
        }
    )
    llm.enqueue({"generated_text": "We could not find that invoice."})
    deps = make_test_deps(tickets=store, llm=llm)
    final = await build_graph(deps).ainvoke({"raw_payload": _intent_payload("msg-intent-ok")})
    ticket = store.get_by_id(UUID(final["ticket_id"]))
    assert ticket is not None
    assert ticket.intent is Intent.PAYMENT_STATUS
    assert ticket.assigned_operator_id == "op_joao"
    assert final["skip_identity"] is False
    actions = [e.action for e in deps.audit.get_by_ticket_id(ticket.id)]
    assert AuditAction.IDENTIFY in actions
    assert AuditAction.MINE in actions
    assert AuditAction.RESOLVE in actions


@pytest.mark.asyncio
async def test_unknown_intent_skips_identity():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": True, "confidence": 0.95})
    llm.enqueue({"intent": "unknown", "confidence": 0.9, "language": "en"})
    llm.enqueue({"generated_text": "We could not find that invoice."})
    deps = make_test_deps(tickets=store, llm=llm)
    final = await build_graph(deps).ainvoke({"raw_payload": _intent_payload("msg-intent-unk")})
    assert final["skip_identity"] is True
    ticket = store.get_by_id(UUID(final["ticket_id"]))
    actions = [e.action for e in deps.audit.get_by_ticket_id(ticket.id)]
    assert AuditAction.IDENTIFY not in actions
    assert AuditAction.RESOLVE in actions


@pytest.mark.asyncio
async def test_low_confidence_intent_skips_identity():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": True, "confidence": 0.95})
    llm.enqueue({"intent": "payment_status", "confidence": 0.2, "language": "en"})
    llm.enqueue({"generated_text": "We could not find that invoice."})
    deps = make_test_deps(
        tickets=store,
        llm=llm,
        settings=Settings(INTENT_MIN_CONFIDENCE=0.5, SENDER_DOMAIN_WHITELIST="acme-supplies.com"),
    )
    final = await build_graph(deps).ainvoke({"raw_payload": _intent_payload("msg-intent-low")})
    assert final["skip_identity"] is True
    ticket = store.get_by_id(UUID(final["ticket_id"]))
    actions = [e.action for e in deps.audit.get_by_ticket_id(ticket.id)]
    assert AuditAction.IDENTIFY not in actions


@pytest.mark.asyncio
async def test_discard_never_calls_intent_llm():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": False, "confidence": 0.9})
    deps = make_test_deps(tickets=store, llm=llm)
    await build_graph(deps).ainvoke({"raw_payload": _intent_payload("msg-no-intent")})
    assert len(llm.calls) == 1
    assert llm.calls[0]["output_schema"].__name__ == "TriageOutput"


@pytest.mark.asyncio
async def test_delegate_never_runs_resolution_stub():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": True, "confidence": 0.95})
    llm.enqueue({"intent": "payment_status", "confidence": 0.9, "language": "en"})
    senders = MockSenderDirectory(
        senders=[
            Sender(
                id="snd-x",
                email="other@vendor.com",
                name="Other",
                company="Vendor",
            )
        ],
        rules=[
            RoutingRule(
                id="rule-x",
                operator_id="op_other",
                email="other@vendor.com",
                domain="vendor.com",
            )
        ],
    )
    deps = make_test_deps(
        tickets=store,
        llm=llm,
        senders=senders,
        settings=Settings(
            DEFAULT_OPERATOR_ID="op_joao",
            SENDER_DOMAIN_WHITELIST="vendor.com",
        ),
    )
    final = await build_graph(deps).ainvoke(
        {
            "raw_payload": {
                "thread_id": "th-del",
                "message_id": "msg-del",
                "from": "other@vendor.com",
                "subject": "Invoice",
                "body": "Pay",
            }
        }
    )
    ticket = store.get_by_id(UUID(final["ticket_id"]))
    assert ticket.status is TicketStatus.DELEGATED
    actions = [e.action for e in deps.audit.get_by_ticket_id(ticket.id)]
    assert AuditAction.DELEGATE in actions
    assert AuditAction.RESOLVE not in actions


def test_postgres_audit_rows_for_happy_path():
    llm = MockLLMAdapter()
    llm.enqueue({"is_ap": True, "confidence": 0.95})
    llm.enqueue({"intent": "payment_status", "confidence": 0.9, "language": "en"})
    llm.enqueue({"generated_text": "We could not find that invoice."})
    message_id = f"msg-d4-audit-{uuid4().hex[:8]}"
    engine = create_engine(app_settings.DATABASE_URL, pool_pre_ping=True)
    with Session(engine) as session:
        deps = build_workflow_deps(session, llm=llm)
        import asyncio

        final = asyncio.run(
            build_graph(deps).ainvoke(
                {
                    "raw_payload": {
                        "thread_id": f"th-{message_id}",
                        "message_id": message_id,
                        "from": "billing@acme-supplies.com",
                        "subject": "Invoice",
                        "body": "Pay",
                    }
                }
            )
        )
        rows = AuditRepo(session).get_by_ticket_id(UUID(final["ticket_id"]))
    engine.dispose()
    nodes = {r.node for r in rows}
    assert "ingest" in nodes
    assert "security" in nodes
    assert "thread" in nodes
    assert "triage" in nodes
    assert "intent" in nodes
    assert "resolution" in nodes
    assert "draft" in nodes
    assert "hitl" in nodes
    assert len(rows) >= 5
