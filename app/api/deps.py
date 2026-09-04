from sqlmodel import Session

from app.adapters.mock_email import MockEmailAdapter
from app.adapters.mock_llm import MockLLMAdapter
from app.adapters.mock_sap import MockSAPAdapter
from app.adapters.mock_sender_directory import MockSenderDirectory
from app.adapters.postgres_repos import AuditRepo, DraftRepo
from app.adapters.postgres_tickets import TicketRepo
from app.domain.deps import WorkflowDeps
from app.ports.llm_port import LLMPort
from settings import settings

# Lab default so POST /ingest + worker can reach triage without enqueue.
_DEFAULT_TRIAGE = {"is_ap": True, "confidence": 0.9}
_DEFAULT_INTENT = {
    "intent": "payment_status",
    "confidence": 0.9,
    "language": "en",
    "extracted_ref": "INV-2026-0001",
    "extracted_amount": 1250.0,
}
_DEFAULT_DRAFT = {
    "generated_text": "Thank you. We are reviewing invoice INV-2026-0001.",
}


def build_workflow_deps(
    session: Session,
    *,
    llm: LLMPort | None = None,
) -> WorkflowDeps:
    return WorkflowDeps(
        settings=settings,
        llm=llm
        or MockLLMAdapter(responses=[_DEFAULT_TRIAGE, _DEFAULT_INTENT, _DEFAULT_DRAFT]),
        email=MockEmailAdapter(),
        tickets=TicketRepo(session),
        sap=MockSAPAdapter(),
        audit=AuditRepo(session),
        senders=MockSenderDirectory(),
        drafts=DraftRepo(session),
    )
