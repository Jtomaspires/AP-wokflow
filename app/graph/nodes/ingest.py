"""Ingest node: parse webhook → persist OPEN ticket or stop."""

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, TicketStatus
from app.domain.models import Ticket
from app.graph.state import LabState


def make_ingest_node(deps: WorkflowDeps):
    def ingest(state: LabState) -> dict:
        event = deps.email.parse_webhook(state.get("raw_payload") or {})
        thread_id = (event.thread_id or "").strip()
        message_id = (event.message_id or "").strip()
        auth = {
            "spf_pass": event.spf_pass,
            "dkim_pass": event.dkim_pass,
        }

        if not thread_id or not message_id:
            return {
                "should_stop": True,
                "ticket_id": None,
                "stop_reason": "missing_ids",
                "audit_action": AuditAction.INGEST.value,
                "audit_metadata": {"reason": "missing_ids"},
                **auth,
            }

        existing = deps.tickets.get_by_message_id(message_id)
        if existing is not None:
            return {
                "should_stop": True,
                "ticket_id": str(existing.id),
                "stop_reason": "duplicate",
                "audit_action": AuditAction.INGEST.value,
                "audit_metadata": {"reason": "duplicate"},
                **auth,
            }

        saved = deps.tickets.save_ticket(
            Ticket(
                thread_id=thread_id,
                message_id=message_id,
                sender_email=event.from_email,
                subject=event.subject,
                body=event.body,
                received_at=event.received_at,
                status=TicketStatus.OPEN,
            )
        )
        return {
            "should_stop": False,
            "ticket_id": str(saved.id),
            "stop_reason": None,
            "audit_action": AuditAction.INGEST.value,
            "audit_metadata": {"reason": "created"},
            **auth,
        }

    return ingest
