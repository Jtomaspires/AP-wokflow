"""Security node: sender-domain whitelist only (no SPF/DKIM in this lab).

If ``SECURITY_CHECK_ENABLED`` is false, the ticket stays OPEN and the graph
continues. Unknown domain + flag on → ``quarantined`` and stop.
"""

from datetime import UTC, datetime
from uuid import UUID

from app.domain.deps import WorkflowDeps
from app.domain.enums import TicketStatus
from app.graph.state import LabState


def _whitelist(csv: str) -> set[str]:
    return {part.strip().lower() for part in csv.split(",") if part.strip()}


def _sender_domain(email: str) -> str:
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].strip().lower()


def make_security_node(deps: WorkflowDeps):
    def security(state: LabState) -> dict:
        raw_id = state.get("ticket_id")
        if not raw_id:
            return {"should_stop": True, "stop_reason": "missing_ticket"}

        ticket = deps.tickets.get_by_id(UUID(raw_id))
        if ticket is None:
            return {"should_stop": True, "stop_reason": "missing_ticket"}

        if not deps.settings.SECURITY_CHECK_ENABLED:
            return {
                "should_stop": False,
                "ticket_id": str(ticket.id),
                "stop_reason": None,
            }

        if _sender_domain(ticket.sender_email) in _whitelist(
            deps.settings.SENDER_DOMAIN_WHITELIST
        ):
            return {
                "should_stop": False,
                "ticket_id": str(ticket.id),
                "stop_reason": None,
            }

        ticket.status = TicketStatus.QUARANTINED
        ticket.updated_at = datetime.now(UTC)
        saved = deps.tickets.save_ticket(ticket)
        return {
            "should_stop": True,
            "ticket_id": str(saved.id),
            "stop_reason": "quarantined",
        }

    return security
