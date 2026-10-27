"""Security: whitelist + optional SPF/DKIM (assistant parity)."""

from datetime import UTC, datetime

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, TicketStatus
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState


def _whitelist(csv: str) -> set[str]:
    return {part.strip().lower() for part in csv.split(",") if part.strip()}


def _sender_domain(email: str) -> str:
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].strip().lower()


def make_security_node(deps: WorkflowDeps):
    def security(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()

        # checks off — pass through
        if not deps.settings.SECURITY_CHECK_ENABLED:
            return {
                "should_stop": False,
                "ticket_id": str(ticket.id),
                "stop_reason": None,
                "audit_action": AuditAction.PASS.value,
                "audit_metadata": {"reason": "security_disabled"},
            }

        # domain not on the list
        if _sender_domain(ticket.sender_email) not in _whitelist(
            deps.settings.SENDER_DOMAIN_WHITELIST
        ):
            ticket.status = TicketStatus.QUARANTINED
            ticket.updated_at = datetime.now(UTC)
            saved = deps.tickets.save_ticket(ticket)
            return {
                "should_stop": True,
                "ticket_id": str(saved.id),
                "stop_reason": "quarantined",
                "audit_action": AuditAction.QUARANTINE.value,
                "audit_metadata": {"reason": "whitelist"},
            }

        if deps.settings.SPF_DKIM_ENABLED:
            spf = state.get("spf_pass")
            dkim = state.get("dkim_pass")
            spf_ok = spf is True
            dkim_ok = dkim is True
            # both failed — quarantine
            if not spf_ok and not dkim_ok:
                ticket.status = TicketStatus.QUARANTINED
                ticket.updated_at = datetime.now(UTC)
                saved = deps.tickets.save_ticket(ticket)
                return {
                    "should_stop": True,
                    "ticket_id": str(saved.id),
                    "stop_reason": "quarantined",
                    "audit_action": AuditAction.QUARANTINE.value,
                    "audit_metadata": {"reason": "spf_dkim_fail"},
                }
            # only one failed — let it through, ding confidence later
            if not spf_ok or not dkim_ok:
                return {
                    "should_stop": False,
                    "ticket_id": str(ticket.id),
                    "stop_reason": None,
                    "spf_dkim_penalty": 0.2,
                    "audit_action": AuditAction.PASS.value,
                    "audit_metadata": {"reason": "spf_dkim_partial", "penalty": 0.2},
                }

        return {
            "should_stop": False,
            "ticket_id": str(ticket.id),
            "stop_reason": None,
            "audit_action": AuditAction.PASS.value,
            "audit_metadata": {"reason": "whitelist_ok"},
        }

    return security
