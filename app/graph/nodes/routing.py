"""Routing: MINE → resolution stub, or DELEGATE and stop."""

from datetime import UTC, datetime

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, TicketStatus
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState


def make_routing_node(deps: WorkflowDeps):
    def routing(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()

        domain = ""
        if "@" in ticket.sender_email:
            domain = ticket.sender_email.rsplit("@", 1)[-1]
        rule = deps.senders.get_routing_rule(email=ticket.sender_email, domain=domain or None)
        default_op = deps.settings.DEFAULT_OPERATOR_ID
        operator_id = rule.operator_id if rule is not None else default_op
        ticket.assigned_operator_id = operator_id
        ticket.updated_at = datetime.now(UTC)

        if operator_id != default_op:
            ticket.status = TicketStatus.DELEGATED
            saved = deps.tickets.save_ticket(ticket)
            return {
                "should_stop": True,
                "ticket_id": str(saved.id),
                "stop_reason": "delegated",
                "route": "end",
                "audit_action": AuditAction.DELEGATE.value,
                "audit_metadata": {"operator_id": operator_id},
            }

        saved = deps.tickets.save_ticket(ticket)
        return {
            "should_stop": False,
            "ticket_id": str(saved.id),
            "stop_reason": None,
            "route": "resolution",
            "audit_action": AuditAction.MINE.value,
            "audit_metadata": {"operator_id": operator_id},
        }

    return routing
