"""Shared WorkflowDeps for graph/node tests (seven ports)."""

from app.adapters.memory_audit_store import InMemoryAuditStore
from app.adapters.memory_draft_store import InMemoryDraftStore
from app.adapters.memory_ticket_store import InMemoryTicketStore
from app.adapters.mock_email import MockEmailAdapter
from app.adapters.mock_llm import MockLLMAdapter
from app.adapters.mock_sap import MockSAPAdapter
from app.adapters.mock_sender_directory import MockSenderDirectory
from app.domain.deps import WorkflowDeps
from settings import Settings


def make_test_deps(**overrides) -> WorkflowDeps:
    values = dict(
        settings=Settings(),
        llm=MockLLMAdapter(),
        email=MockEmailAdapter(),
        tickets=InMemoryTicketStore(),
        sap=MockSAPAdapter(),
        audit=InMemoryAuditStore(),
        senders=MockSenderDirectory(),
        drafts=InMemoryDraftStore(),
    )
    values.update(overrides)
    return WorkflowDeps(**values)
