"""Resolution placeholder — Day 5 fills matching. Ticket stays OPEN."""

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState


def make_resolution_node(deps: WorkflowDeps):
    def resolution(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()
        return {
            "should_stop": False,
            "ticket_id": str(ticket.id),
            "stop_reason": None,
            "audit_action": AuditAction.RESOLVE.value,
            "audit_metadata": {"stub": True},
        }

    return resolution
