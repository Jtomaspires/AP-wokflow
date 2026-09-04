"""Send after HITL approve. Mock unless NYLAS_SEND_ENABLED (still no live Nylas)."""

from datetime import UTC, datetime
from typing import Protocol

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
        draft = drafts[-1]
        action = HumanReviewAction(state.get("review_action") or HumanReviewAction.APPROVE.value)
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
        nylas = bool(deps.settings.NYLAS_SEND_ENABLED)
        deps.audit.append(
            AuditEntry(
                ticket_id=ticket.id,
                node="send",
                action=AuditAction.SEND,
                metadata={
                    "mock": not nylas,
                    "nylas": nylas,
                    "review_action": action.value,
                },
            )
        )
        return {
            "should_stop": True,
            "ticket_id": str(ticket.id),
            "stop_reason": "sent",
            "status": ticket.status.value,
        }

    return send
