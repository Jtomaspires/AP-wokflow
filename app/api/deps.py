from sqlmodel import Session

from app.adapters.mock_email import MockEmailAdapter
from app.adapters.mock_llm import MockLLMAdapter
from app.adapters.postgres_tickets import TicketRepo
from app.domain.deps import WorkflowDeps
from settings import settings


def build_workflow_deps(session: Session) -> WorkflowDeps:
    return WorkflowDeps(
        settings=settings,
        email=MockEmailAdapter(),
        tickets=TicketRepo(session),
        llm=MockLLMAdapter(),
    )