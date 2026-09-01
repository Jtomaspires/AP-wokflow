"""Security node — whitelist + SECURITY_CHECK_ENABLED (Day 2)."""

from uuid import UUID

from app.adapters.memory_ticket_store import InMemoryTicketStore
from app.adapters.mock_email import MockEmailAdapter
from app.adapters.mock_llm import MockLLMAdapter
from app.domain.deps import WorkflowDeps
from app.domain.enums import TicketStatus
from app.graph.nodes.ingest import make_ingest_node
from app.graph.nodes.security import make_security_node
from settings import Settings


def _deps(
    store: InMemoryTicketStore,
    *,
    security_enabled: bool = True,
    whitelist: str = "acme-supplies.com",
) -> WorkflowDeps:
    return WorkflowDeps(
        settings=Settings(
            SECURITY_CHECK_ENABLED=security_enabled,
            SENDER_DOMAIN_WHITELIST=whitelist,
        ),
        email=MockEmailAdapter(),
        tickets=store,
        llm=MockLLMAdapter(),
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
