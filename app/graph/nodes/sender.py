"""Sender identity: email 0.9, unique domain 0.6, else unknown 0.0. Never stops."""

from datetime import UTC, datetime

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState


def make_sender_node(deps: WorkflowDeps):
    def sender(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()

        found = deps.senders.get_by_email(ticket.sender_email)
        score = 0.0
        sender_id = None
        if found is not None:
            sender_id = found.id
            score = 0.9
        else:
            domain = ""
            if "@" in ticket.sender_email:
                domain = ticket.sender_email.rsplit("@", 1)[-1]
            matches = deps.senders.get_by_domain(domain) if domain else []
            if len(matches) == 1:
                sender_id = matches[0].id
                score = 0.6

        ticket.updated_at = datetime.now(UTC)
        saved = deps.tickets.save_ticket(ticket)
        return {
            "should_stop": False,
            "ticket_id": str(saved.id),
            "stop_reason": None,
            "sender_id": sender_id,
            "route": "routing",
            "audit_action": AuditAction.IDENTIFY.value,
            "audit_confidence": score,
            "audit_metadata": {"sender_id": sender_id, "score": score},
        }

    return sender
