"""Thread: continuation vs new vs escalated stop."""

from datetime import UTC, datetime

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, TicketStatus
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState

_ACTIVE = {TicketStatus.OPEN, TicketStatus.AWAITING_HUMAN}


def make_thread_node(deps: WorkflowDeps):
    def thread(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()

        others = [
            t
            for t in deps.tickets.list_by_thread_id(ticket.thread_id)
            if t.id != ticket.id
        ]
        others.sort(key=lambda t: t.updated_at, reverse=True)

        escalated = next((t for t in others if t.status is TicketStatus.ESCALATED), None)
        if escalated is not None:
            escalated.body = f"{escalated.body}\n\n---\n\n{ticket.body}"
            escalated.updated_at = datetime.now(UTC)
            deps.tickets.save_ticket(escalated)
            ticket.status = TicketStatus.DISCARDED
            ticket.updated_at = datetime.now(UTC)
            deps.tickets.save_ticket(ticket)
            return {
                "should_stop": True,
                "ticket_id": str(escalated.id),
                "stop_reason": "escalated_thread",
                "route": "end",
                "is_thread_continuation": True,
                "audit_action": AuditAction.THREAD.value,
                "audit_metadata": {"reason": "escalated"},
            }

        active = next((t for t in others if t.status in _ACTIVE), None)
        resolved = next((t for t in others if t.status is TicketStatus.RESOLVED), None)
        prior = active or resolved
        if prior is not None:
            if prior.status is TicketStatus.RESOLVED:
                prior.status = TicketStatus.OPEN
            prior.is_thread_continuation = True
            prior.body = f"{prior.body}\n\n---\n\n{ticket.body}"
            prior.subject = ticket.subject
            prior.updated_at = datetime.now(UTC)
            deps.tickets.save_ticket(prior)
            ticket.status = TicketStatus.DISCARDED
            ticket.is_thread_continuation = True
            ticket.updated_at = datetime.now(UTC)
            deps.tickets.save_ticket(ticket)
            return {
                "should_stop": False,
                "ticket_id": str(prior.id),
                "stop_reason": None,
                "route": "resolution",
                "is_thread_continuation": True,
                "audit_action": AuditAction.THREAD.value,
                "audit_metadata": {"reason": "continuation"},
            }

        return {
            "should_stop": False,
            "ticket_id": str(ticket.id),
            "stop_reason": None,
            "route": "triage",
            "is_thread_continuation": False,
            "audit_action": AuditAction.THREAD.value,
            "audit_metadata": {"reason": "new"},
        }

    return thread
