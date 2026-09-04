"""HITL: always park AWAITING_HUMAN. Send is not on the inbound spine."""

from datetime import UTC, datetime

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, TicketStatus
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState


def make_hitl_node(deps: WorkflowDeps):
    def hitl(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()
        ticket.status = TicketStatus.AWAITING_HUMAN
        ticket.updated_at = datetime.now(UTC)
        saved = deps.tickets.save_ticket(ticket)
        return {
            "should_stop": True,
            "ticket_id": str(saved.id),
            "stop_reason": "awaiting_human",
            "audit_action": AuditAction.HITL.value,
            "audit_metadata": {"skip_draft": bool(state.get("skip_draft"))},
        }

    return hitl
