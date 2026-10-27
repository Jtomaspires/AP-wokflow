"""Send after HITL approve. Live Nylas only when the flag, key, and grant are set."""

from datetime import UTC, datetime
from typing import Protocol

from app.adapters.nylas_send import send_reply
from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, HumanReviewAction, TicketStatus
from app.domain.models import AuditEntry, HumanReview
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState


class ReviewStore(Protocol):
    def save(self, review: HumanReview) -> HumanReview: ...


def make_send_node(deps: WorkflowDeps, reviews: ReviewStore):
    def send(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()
        drafts = deps.drafts.get_by_ticket_id(ticket.id)
        if not drafts:
            return {"should_stop": True, "stop_reason": "no_draft", "ticket_id": str(ticket.id)}
        draft = drafts[-1]  # latest only
        action = HumanReviewAction(state.get("review_action") or HumanReviewAction.APPROVE.value)

        def failed(metadata: dict) -> dict:
            # log the miss, leave ticket status alone
            deps.audit.append(
                AuditEntry(
                    ticket_id=ticket.id,
                    node="send",
                    action=AuditAction.SEND,
                    metadata=metadata,
                )
            )
            return {
                "should_stop": True,
                "ticket_id": str(ticket.id),
                "stop_reason": "send_failed",
                "status": ticket.status.value,
            }

        if deps.settings.NYLAS_SEND_ENABLED:
            api_key = deps.settings.NYLAS_API_KEY
            grant_id = deps.settings.NYLAS_GRANT_ID
            # flag on but no creds — fail closed
            if not api_key or not grant_id:
                return failed(
                    {
                        "mock": False,
                        "nylas": False,
                        "error": "nylas_not_configured",
                        "review_action": action.value,
                    }
                )
            try:
                send_reply(
                    to_email=draft.to_email,
                    subject=ticket.subject,
                    body=draft.final_text or draft.generated_text,
                    reply_to_message_id=ticket.provider_message_id,
                    api_key=api_key,
                    grant_id=grant_id,
                    api_uri=deps.settings.NYLAS_API_URI,
                )
            except OSError as exc:
                metadata: dict = {
                    "mock": False,
                    "nylas": False,
                    "error": str(exc),
                    "review_action": action.value,
                }
                code = getattr(exc, "code", None)
                if code is not None:
                    metadata["status_code"] = code
                return failed(metadata)
            sent = {
                "mock": False,
                "nylas": True,
                "to": draft.to_email,
                # in-thread reply when we have the provider id
                "mode": "reply" if ticket.provider_message_id else "new_message",
                "review_action": action.value,
            }
        else:
            # dry run
            sent = {"mock": True, "nylas": False, "review_action": action.value}

        # review row, then mark resolved
        reviews.save(
            HumanReview(
                ticket_id=ticket.id,
                draft_id=draft.id,
                action=action,
                operator_id=state.get("operator_id") or deps.settings.DEFAULT_OPERATOR_ID,
            )
        )
        ticket.status = TicketStatus.RESOLVED
        ticket.updated_at = datetime.now(UTC)
        deps.tickets.save_ticket(ticket)
        deps.audit.append(
            AuditEntry(
                ticket_id=ticket.id,
                node="send",
                action=AuditAction.SEND,
                metadata=sent,
            )
        )
        return {
            "should_stop": True,
            "ticket_id": str(ticket.id),
            "stop_reason": "sent",
            "status": ticket.status.value,
        }

    return send
