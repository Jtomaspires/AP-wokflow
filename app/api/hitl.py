"""HITL approve/escalate. Send is not on the inbound graph (option 2)."""

from datetime import UTC, datetime
from uuid import UUID

from typing import Protocol

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, HumanReviewAction, TicketStatus
from app.domain.models import AuditEntry, HumanReview
from app.graph.nodes.send import make_send_node


class ReviewStore(Protocol):
    def save(self, review: HumanReview) -> HumanReview: ...


class HitlConflictError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class HitlService:
    def __init__(self, deps: WorkflowDeps, reviews: ReviewStore) -> None:
        self.deps = deps
        self.reviews = reviews
        self._send = make_send_node(deps, reviews)

    def _ticket(self, ticket_id: UUID):
        ticket = self.deps.tickets.get_by_id(ticket_id)
        if ticket is None:
            return None
        return ticket

    def _require_awaiting(self, ticket) -> None:
        if ticket.status is not TicketStatus.AWAITING_HUMAN:
            raise HitlConflictError("ticket is not awaiting human review")

    def approve(
        self,
        ticket_id: UUID,
        *,
        operator_id: str,
        final_text: str | None = None,
    ) -> dict:
        ticket = self._ticket(ticket_id)
        if ticket is None:
            return None  # type: ignore[return-value]
        self._require_awaiting(ticket)
        drafts = self.deps.drafts.get_by_ticket_id(ticket.id)
        if not drafts:
            raise HitlConflictError("no draft to approve")
        draft = drafts[-1]
        action = HumanReviewAction.APPROVE
        if final_text:
            draft.final_text = final_text
            draft.edited_by_human = True
            self.deps.drafts.save(draft)
            action = HumanReviewAction.APPROVE_EDIT
        audit_action = (
            AuditAction.APPROVE_EDIT if action is HumanReviewAction.APPROVE_EDIT else AuditAction.APPROVE
        )
        self.deps.audit.append(
            AuditEntry(
                ticket_id=ticket.id,
                node="hitl",
                action=audit_action,
                metadata={"operator_id": operator_id},
            )
        )
        return self._send(
            {
                "ticket_id": str(ticket.id),
                "review_action": action.value,
                "operator_id": operator_id,
            }
        )

    def escalate(self, ticket_id: UUID, *, operator_id: str) -> dict:
        ticket = self._ticket(ticket_id)
        if ticket is None:
            return None  # type: ignore[return-value]
        self._require_awaiting(ticket)
        drafts = self.deps.drafts.get_by_ticket_id(ticket.id)
        if drafts:
            self.reviews.save(
                HumanReview(
                    ticket_id=ticket.id,
                    draft_id=drafts[-1].id,
                    action=HumanReviewAction.ESCALATED_TO_EMAIL,
                    operator_id=operator_id,
                )
            )
        ticket.status = TicketStatus.ESCALATED
        ticket.updated_at = datetime.now(UTC)
        self.deps.tickets.save_ticket(ticket)
        self.deps.audit.append(
            AuditEntry(
                ticket_id=ticket.id,
                node="hitl",
                action=AuditAction.ESCALATE,
                metadata={"operator_id": operator_id},
            )
        )
        return {"ticket_id": str(ticket.id), "status": ticket.status.value, "should_stop": True}
