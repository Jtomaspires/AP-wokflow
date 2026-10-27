from sqlmodel import Session

from app.adapters.mock_email import MockEmailAdapter
from app.adapters.mock_llm import MockLLMAdapter
from app.adapters.mock_sap import MockSAPAdapter
from app.adapters.mock_sender_directory import MockSenderDirectory
from app.adapters.openai_llm import OpenAILLMAdapter
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
    "generated_text": "Please review invoice INV-2026-0001. It is still in approval.",
}


def _default_llm() -> LLMPort:
    if not settings.LLM_PRIMARY_API_KEY:
        return MockLLMAdapter(responses=[_DEFAULT_TRIAGE, _DEFAULT_INTENT, _DEFAULT_DRAFT])
    fallback = None
    if settings.LLM_FALLBACK_MODEL and settings.LLM_FALLBACK_API_KEY:
        fallback = OpenAILLMAdapter(
            api_key=settings.LLM_FALLBACK_API_KEY,
            model=settings.LLM_FALLBACK_MODEL,
            base_url=settings.LLM_FALLBACK_BASE_URL,
            timeout_s=settings.LLM_TIMEOUT_S,
            retry_backoff_s=settings.LLM_RETRY_BACKOFF_S,
        )
    return OpenAILLMAdapter(
        api_key=settings.LLM_PRIMARY_API_KEY,
        model=settings.LLM_PRIMARY_MODEL,
        base_url=settings.LLM_PRIMARY_BASE_URL,
        timeout_s=settings.LLM_TIMEOUT_S,
        retry_backoff_s=settings.LLM_RETRY_BACKOFF_S,
        fallback=fallback,
    )


def build_workflow_deps(
    session: Session,
    *,
    llm: LLMPort | None = None,
) -> WorkflowDeps:
    return WorkflowDeps(
        settings=settings,
        llm=llm or _default_llm(),
        email=MockEmailAdapter(),
        tickets=TicketRepo(session),
        sap=MockSAPAdapter(),
        audit=AuditRepo(session),
        senders=MockSenderDirectory(),
        drafts=DraftRepo(session),
    )
