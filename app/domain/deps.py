"""Runtime ports injected into the workflow (not persisted)."""

from dataclasses import dataclass

from app.ports.email_port import EmailPort
from app.ports.llm_port import LLMPort
from app.ports.ticket_store_port import TicketStorePort
from settings import Settings


@dataclass
class WorkflowDeps:
    settings: Settings
    email: EmailPort
    tickets: TicketStorePort
    llm: LLMPort
