"""Routing: MINE → resolution, or DELEGATE and stop."""

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
        no_rule_outcome = None
        # no rule + hitl mode — don't assign anyone, still continue
        if rule is None and deps.settings.ROUTING_NO_RULE_BEHAVIOUR == "hitl":
            ticket.assigned_operator_id = None
            ticket.updated_at = datetime.now(UTC)
            saved = deps.tickets.save_ticket(ticket)
            return {
                "should_stop": False,
                "ticket_id": str(saved.id),
                "stop_reason": None,
                "route": "resolution",
                "routing_outcome": "no_rule_hitl",
                "audit_action": AuditAction.MINE.value,
                "audit_metadata": {"reason": "no_rule_hitl", "operator_id": None},
            }
        if rule is None:
            # no rule otherwise — default operator
            operator_id = default_op
            no_rule_outcome = "no_rule_default"
        else:
            operator_id = rule.operator_id
        ticket.assigned_operator_id = operator_id
        ticket.updated_at = datetime.now(UTC)

        # someone else's queue — stop
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

        # ours — on to resolution
        saved = deps.tickets.save_ticket(ticket)
        metadata = {"operator_id": operator_id}
        update = {
            "should_stop": False,
            "ticket_id": str(saved.id),
            "stop_reason": None,
            "route": "resolution",
            "audit_action": AuditAction.MINE.value,
            "audit_metadata": metadata,
        }
        if no_rule_outcome is not None:
            metadata["reason"] = no_rule_outcome
            update["routing_outcome"] = no_rule_outcome
        return update

    return routing
