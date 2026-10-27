"""Ingest node: parse webhook → persist OPEN ticket or stop."""

import hashlib

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, TicketStatus
from app.domain.events import IncomingEmail
from app.domain.models import Ticket
from app.graph.state import LabState


def _content_hash(event: IncomingEmail) -> str:
    # same sender / subject / opening — treat as the same mail
    raw = f"{event.from_email}|{event.subject}|{(event.body or '')[:300]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def make_ingest_node(deps: WorkflowDeps):
    def ingest(state: LabState) -> dict:
        event = deps.email.parse_webhook(state.get("raw_payload") or {})
        thread_id = (event.thread_id or "").strip()
        message_id = (event.message_id or "").strip()
        auth = {
            "spf_pass": event.spf_pass,
            "dkim_pass": event.dkim_pass,
        }

        # can't thread it without both ids
        if not thread_id or not message_id:
            return {
                "should_stop": True,
                "ticket_id": None,
                "stop_reason": "missing_ids",
                "audit_action": AuditAction.INGEST.value,
                "audit_metadata": {"reason": "missing_ids"},
                **auth,
            }

        # exact message id already stored
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

        # same content, different id (retries)
        content_hash = _content_hash(event)
        existing_hash = deps.tickets.get_by_content_hash(content_hash)
        if existing_hash is not None:
            return {
                "should_stop": True,
                "ticket_id": str(existing_hash.id),
                "stop_reason": "duplicate",
                "audit_action": AuditAction.INGEST.value,
                "audit_metadata": {"reason": "content_duplicate"},
                **auth,
            }

        saved = deps.tickets.save_ticket(
            Ticket(
                thread_id=thread_id,
                message_id=message_id,
                provider_message_id=event.provider_message_id,
                sender_email=event.from_email,
                subject=event.subject,
                body=event.body,
                received_at=event.received_at,
                status=TicketStatus.OPEN,
                content_hash=content_hash,
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
