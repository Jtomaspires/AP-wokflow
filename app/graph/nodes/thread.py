"""Thread: continuation vs new vs escalated stop."""

from datetime import UTC, datetime

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, TicketStatus
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState

_ACTIVE = {TicketStatus.OPEN, TicketStatus.AWAITING_HUMAN}
_TRUNCATED = "[...earlier messages truncated...]"


def _truncate_history(body: str, max_chars: int) -> str:
    # under the cap, leave it
    if len(body) <= max_chars:
        return body
    # keep the tail, snap to a message break if there is one
    tail = body[-max_chars:]
    sep = "\n\n---\n\n"
    idx = tail.find(sep)
    if idx != -1:
        tail = tail[idx + len(sep) :]
    return f"{_TRUNCATED}\n\n---\n\n{tail}"


def make_thread_node(deps: WorkflowDeps):
    def thread(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()

        # other tickets on this thread, newest first
        others = [
            t
            for t in deps.tickets.list_by_thread_id(ticket.thread_id)
            if t.id != ticket.id
        ]
        others.sort(key=lambda t: t.updated_at, reverse=True)

        # already escalated — fold this mail in, drop the new ticket
        escalated = next((t for t in others if t.status is TicketStatus.ESCALATED), None)
        if escalated is not None:
            escalated.body = _truncate_history(
                f"{escalated.body}\n\n---\n\n{ticket.body}",
                deps.settings.THREAD_MAX_HISTORY_CHARS,
            )
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

        # open / awaiting-human first, else a resolved one we can reopen
        active = next((t for t in others if t.status in _ACTIVE), None)
        resolved = next((t for t in others if t.status is TicketStatus.RESOLVED), None)
        prior = active or resolved
        if prior is not None:
            # resolved comes back as open
            if prior.status is TicketStatus.RESOLVED:
                prior.status = TicketStatus.OPEN
            prior.is_thread_continuation = True
            # fold this mail into the old ticket, discard the new one
            prior.body = _truncate_history(
                f"{prior.body}\n\n---\n\n{ticket.body}",
                deps.settings.THREAD_MAX_HISTORY_CHARS,
            )
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

        # nothing prior — fresh ticket, off to triage
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
