"""Ingest node: parse webhook → persist OPEN ticket or stop.

Missing ``thread_id`` or ``message_id``: ``should_stop=True`` and **no** ticket is
created (rejected before persist). Duplicate ``message_id``: stop and reuse the
existing ticket id.
"""

from app.domain.deps import WorkflowDeps
from app.domain.enums import TicketStatus
from app.domain.models import Ticket
from app.graph.state import LabState


def make_ingest_node(deps: WorkflowDeps):
    def ingest(state: LabState) -> dict:
        event = deps.email.parse_webhook(state.get("raw_payload") or {})
        thread_id = (event.thread_id or "").strip()
        message_id = (event.message_id or "").strip()

        if not thread_id or not message_id:
            return {
                "should_stop": True,
                "ticket_id": None,
                "stop_reason": "missing_ids",
            }

        existing = deps.tickets.get_by_message_id(message_id)
        if existing is not None:
            return {
                "should_stop": True,
                "ticket_id": str(existing.id),
                "stop_reason": "duplicate",
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
        }

    return ingest
