"""Postgres audit, draft, and HITL review repos."""

from uuid import UUID

from sqlmodel import Session, select

from app.adapters.db_models import AuditEntryTable, HumanReviewTable, ResponseDraftTable
from app.domain.enums import AuditAction, DraftTarget, HumanReviewAction
from app.domain.models import AuditEntry, HumanReview, ResponseDraft
from app.ports.audit_port import AuditPort
from app.ports.draft_port import DraftPort


class AuditRepo(AuditPort):
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, entry: AuditEntry) -> AuditEntry:
        row = AuditEntryTable(
            id=entry.id,
            ticket_id=entry.ticket_id,
            node=entry.node,
            action=entry.action.value,
            confidence=entry.confidence,
            metadata_json=entry.metadata,
            created_at=entry.created_at,
        )
        self.session.add(row)
        self.session.commit()
        return entry

    def get_by_ticket_id(self, ticket_id: UUID) -> list[AuditEntry]:
        rows = self.session.exec(
            select(AuditEntryTable).where(AuditEntryTable.ticket_id == ticket_id)
        ).all()
        return [
            AuditEntry(
                id=row.id,
                ticket_id=row.ticket_id,
                node=row.node,
                action=AuditAction(row.action),
                confidence=row.confidence,
                metadata=row.metadata_json or {},
                created_at=row.created_at,
            )
            for row in rows
        ]


class DraftRepo(DraftPort):
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, draft: ResponseDraft) -> ResponseDraft:
        self.session.merge(
            ResponseDraftTable(
                id=draft.id,
                ticket_id=draft.ticket_id,
                target=draft.target.value,
                to_email=draft.to_email,
                generated_text=draft.generated_text,
                final_text=draft.final_text,
                edited_by_human=draft.edited_by_human,
                operator_notes=draft.operator_notes,
                attach_invoice_pdf=draft.attach_invoice_pdf,
                attach_payment_proof=draft.attach_payment_proof,
                created_at=draft.created_at,
            )
        )
        self.session.commit()
        return draft

    def get_by_ticket_id(self, ticket_id: UUID) -> list[ResponseDraft]:
        rows = self.session.exec(
            select(ResponseDraftTable).where(ResponseDraftTable.ticket_id == ticket_id)
        ).all()
        return [
            ResponseDraft(
                id=row.id,
                ticket_id=row.ticket_id,
                target=DraftTarget(row.target),
                to_email=row.to_email,
                generated_text=row.generated_text,
                final_text=row.final_text,
                edited_by_human=row.edited_by_human,
                operator_notes=row.operator_notes,
                attach_invoice_pdf=row.attach_invoice_pdf,
                attach_payment_proof=row.attach_payment_proof,
                created_at=row.created_at,
            )
            for row in rows
        ]


class HumanReviewRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, review: HumanReview) -> HumanReview:
        self.session.merge(
            HumanReviewTable(
                id=review.id,
                ticket_id=review.ticket_id,
                draft_id=review.draft_id,
                action=review.action.value,
                operator_id=review.operator_id,
                notes=review.notes,
                created_at=review.created_at,
            )
        )
        self.session.commit()
        return review

    def get_by_ticket_id(self, ticket_id: UUID) -> list[HumanReview]:
        rows = self.session.exec(
            select(HumanReviewTable).where(HumanReviewTable.ticket_id == ticket_id)
        ).all()
        return [
            HumanReview(
                id=row.id,
                ticket_id=row.ticket_id,
                draft_id=row.draft_id,
                action=HumanReviewAction(row.action),
                operator_id=row.operator_id,
                notes=row.notes,
                created_at=row.created_at,
            )
            for row in rows
        ]
