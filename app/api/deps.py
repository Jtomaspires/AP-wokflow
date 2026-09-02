from sqlmodel import Session

from app.adapters.mock_email import MockEmailAdapter
from app.adapters.mock_llm import MockLLMAdapter
from app.adapters.postgres_tickets import TicketRepo
from app.domain.deps import WorkflowDeps
from app.ports.llm_port import LLMPort
from settings import settings


def build_workflow_deps(
    session: Session,
    *,
    llm: LLMPort | None = None,
) -> WorkflowDeps:
    return WorkflowDeps(
        settings=settings,
        email=MockEmailAdapter(),
        tickets=TicketRepo(session),
        llm=llm or MockLLMAdapter(),
    )