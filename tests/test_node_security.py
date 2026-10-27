"""Security node — whitelist + SECURITY_CHECK_ENABLED (Day 2)."""

from uuid import UUID

import pytest

from app.adapters.memory_ticket_store import InMemoryTicketStore
from app.adapters.mock_llm import MockLLMAdapter
from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, TicketStatus
from app.graph.app import build_graph
from app.graph.nodes.ingest import make_ingest_node
from app.graph.nodes.security import make_security_node
from settings import Settings
from tests.helpers import make_test_deps


def _deps(
    store: InMemoryTicketStore,
    *,
    security_enabled: bool = True,
    whitelist: str = "acme-supplies.com",
    spf_dkim_enabled: bool = False,
) -> WorkflowDeps:
    return make_test_deps(
        settings=Settings(
            SECURITY_CHECK_ENABLED=security_enabled,
            SENDER_DOMAIN_WHITELIST=whitelist,
            SPF_DKIM_ENABLED=spf_dkim_enabled,
        ),
        tickets=store,
    )


def _payload(from_email: str, message_id: str = "msg-1") -> dict:
    return {
        "thread_id": "thread-1",
        "message_id": message_id,
        "from": from_email,
        "subject": "Invoice",
        "body": "Hello",
    }


def _ingest_then_security(deps: WorkflowDeps, payload: dict) -> tuple[dict, dict]:
    ingest = make_ingest_node(deps)
    security = make_security_node(deps)
    after_ingest = ingest({"raw_payload": payload})
    after_security = security(after_ingest)
    return after_ingest, after_security


def test_whitelisted_domain_continues_open():
    store = InMemoryTicketStore()
    deps = _deps(store)
    after_ingest, after_security = _ingest_then_security(
        deps, _payload("billing@acme-supplies.com")
    )

    assert after_ingest["should_stop"] is False
    assert after_security["should_stop"] is False
    ticket = store.get_by_id(UUID(after_security["ticket_id"]))
    assert ticket is not None
    assert ticket.status is TicketStatus.OPEN


def test_unknown_domain_with_flag_on_quarantines_and_stops():
    store = InMemoryTicketStore()
    deps = _deps(store)
    _, after_security = _ingest_then_security(
        deps, _payload("phish@evil.example", message_id="msg-evil")
    )

    assert after_security["should_stop"] is True
    assert after_security["stop_reason"] == "quarantined"
    ticket = store.get_by_id(UUID(after_security["ticket_id"]))
    assert ticket is not None
    assert ticket.status is TicketStatus.QUARANTINED


def test_flag_off_allows_unknown_domain():
    store = InMemoryTicketStore()
    deps = _deps(store, security_enabled=False)
    _, after_security = _ingest_then_security(
        deps, _payload("phish@evil.example", message_id="msg-off")
    )

    assert after_security["should_stop"] is False
    ticket = store.get_by_id(UUID(after_security["ticket_id"]))
    assert ticket is not None
    assert ticket.status is TicketStatus.OPEN


def test_spf_dkim_both_fail_quarantines():
    store = InMemoryTicketStore()
    deps = _deps(store, spf_dkim_enabled=True)
    payload = _payload("billing@acme-supplies.com", message_id="msg-spf-fail")
    payload["spf_pass"] = False
    payload["dkim_pass"] = False
    _, after_security = _ingest_then_security(deps, payload)
    assert after_security["should_stop"] is True
    ticket = store.get_by_id(UUID(after_security["ticket_id"]))
    assert ticket is not None
    assert ticket.status is TicketStatus.QUARANTINED


def test_spf_dkim_partial_fail_continues_with_penalty():
    store = InMemoryTicketStore()
    deps = _deps(store, spf_dkim_enabled=True)
    payload = _payload("billing@acme-supplies.com", message_id="msg-spf-partial")
    payload["spf_pass"] = False
    payload["dkim_pass"] = True
    _, after_security = _ingest_then_security(deps, payload)
    assert after_security["should_stop"] is False
    assert after_security["spf_dkim_penalty"] == pytest.approx(0.2)
    ticket = store.get_by_id(UUID(after_security["ticket_id"]))
    assert ticket is not None
    assert ticket.status is TicketStatus.OPEN
    assert ticket.confidence is None


def _partial_payload(message_id: str) -> dict:
    return {
        "thread_id": f"thread-{message_id}",
        "message_id": message_id,
        "from": "billing@acme-supplies.com",
        "subject": f"Invoice {message_id}",
        "body": "Please confirm payment status.",
        "spf_pass": False,
        "dkim_pass": True,
    }


def _partial_deps(store: InMemoryTicketStore, llm: MockLLMAdapter) -> WorkflowDeps:
    return make_test_deps(
        tickets=store,
        llm=llm,
        settings=Settings(
            SPF_DKIM_ENABLED=True,
            SENDER_DOMAIN_WHITELIST="acme-supplies.com",
            INTENT_MIN_CONFIDENCE=0.5,
        ),
    )


def _enqueue_spine(llm: MockLLMAdapter, *, intent_confidence: float) -> None:
    llm.enqueue({"is_ap": True, "confidence": 0.95})
    llm.enqueue(
        {
            "intent": "payment_status",
            "confidence": intent_confidence,
            "language": "en",
            "extracted_ref": "INV-1",
            "extracted_amount": 10.0,
        }
    )
    llm.enqueue({"generated_text": "We could not find that invoice."})


@pytest.mark.asyncio
async def test_spf_dkim_partial_fail_reduces_intent_confidence():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    _enqueue_spine(llm, intent_confidence=0.75)
    deps = _partial_deps(store, llm)
    final = await build_graph(deps).ainvoke(
        {"raw_payload": _partial_payload("msg-spf-intent-075")}
    )
    ticket = store.get_by_id(UUID(final["ticket_id"]))
    assert ticket is not None
    assert final["spf_dkim_penalty"] == pytest.approx(0.2)
    assert final["skip_identity"] is False
    assert ticket.confidence == pytest.approx(0.55)
    actions = [entry.action for entry in deps.audit.get_by_ticket_id(ticket.id)]
    assert AuditAction.IDENTIFY in actions


@pytest.mark.asyncio
async def test_spf_dkim_partial_fail_can_flip_skip_identity():
    store = InMemoryTicketStore()
    llm = MockLLMAdapter()
    _enqueue_spine(llm, intent_confidence=0.65)
    deps = _partial_deps(store, llm)
    final = await build_graph(deps).ainvoke(
        {"raw_payload": _partial_payload("msg-spf-intent-065")}
    )
    ticket = store.get_by_id(UUID(final["ticket_id"]))
    assert ticket is not None
    assert final["skip_identity"] is True
    assert ticket.confidence == pytest.approx(0.45)
    actions = [entry.action for entry in deps.audit.get_by_ticket_id(ticket.id)]
    assert AuditAction.IDENTIFY not in actions
    assert AuditAction.MINE not in actions
    assert AuditAction.RESOLVE in actions
