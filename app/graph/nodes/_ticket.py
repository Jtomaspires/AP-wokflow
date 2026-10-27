"""Shared helpers for graph nodes."""

from uuid import UUID

from app.domain.deps import WorkflowDeps
from app.domain.models import Ticket
from app.graph.state import LabState


def load_ticket(deps: WorkflowDeps, state: LabState) -> Ticket | None:
    # state only carries the id
    raw_id = state.get("ticket_id")
    if not raw_id:
        return None
    return deps.tickets.get_by_id(UUID(raw_id))


def missing_ticket() -> dict:
    # upstream didn't leave a ticket
    return {"should_stop": True, "stop_reason": "missing_ticket"}
