"""HITL: always park AWAITING_HUMAN. Send is not on the inbound spine."""

from datetime import UTC, datetime, timedelta

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, TicketStatus
from app.domain.models import Invoice
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState


def _deadline(state: LabState, *, default_hours: int) -> datetime:
    # invoice due date if we have one, else now + default hours
    dump = state.get("invoice_dump")
    if dump and dump.get("due_date"):
        due = Invoice.model_validate(dump).due_date
        if due is not None:
            return datetime(due.year, due.month, due.day, tzinfo=UTC)
    return datetime.now(UTC) + timedelta(hours=default_hours)


def make_hitl_node(deps: WorkflowDeps):
    def hitl(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()
        # park it — send is a later, separate step
        ticket.status = TicketStatus.AWAITING_HUMAN
        ticket.hitl_deadline = _deadline(
            state, default_hours=deps.settings.HITL_DEFAULT_DEADLINE_H
        )
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
