"""Draft: deterministic target, LLM writes generated_text only."""

from datetime import UTC, datetime

from pydantic import BaseModel

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, DraftTarget, InvoiceMatchResult, InvoiceStage, InvoiceStatus
from app.domain.models import Invoice, ResponseDraft
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState
from app.llm.prompts import DRAFT_SYSTEM_PROMPT


class DraftOutput(BaseModel):
    generated_text: str


def pick_target(
    *,
    match_result: InvoiceMatchResult,
    invoice: Invoice | None,
    is_overdue: bool,
    is_near_due: bool,
) -> DraftTarget | None:
    if match_result in {
        InvoiceMatchResult.MULTIPLE,
        InvoiceMatchResult.TOO_MANY,
        InvoiceMatchResult.VAT_DISCREPANCY,
    }:
        return None
    if match_result is InvoiceMatchResult.NOT_FOUND:
        return DraftTarget.INVOICING
    if invoice is None:
        return None
    if invoice.stage is InvoiceStage.IN_APPROVAL:
        if (is_overdue or is_near_due) and invoice.approval_owner_email:
            return DraftTarget.APPROVAL_OWNERS
        if is_overdue and not invoice.approval_owner_email:
            return None
        return DraftTarget.SENDER
    if invoice.stage is InvoiceStage.POSTED:
        if invoice.status is InvoiceStatus.BLOCKED or (
            is_overdue and invoice.status is InvoiceStatus.PENDING
        ):
            return DraftTarget.PAYMENTS
        if invoice.status in {InvoiceStatus.PENDING, InvoiceStatus.PARTIAL} and not is_overdue:
            return DraftTarget.SENDER
        if invoice.status is InvoiceStatus.PAID and invoice.clearing_document:
            return DraftTarget.SENDER
        if invoice.status is InvoiceStatus.PAID and not invoice.clearing_document:
            return None
        return DraftTarget.SENDER
    return DraftTarget.SENDER


def _to_email(deps: WorkflowDeps, target: DraftTarget, ticket, invoice: Invoice | None) -> str:
    if target is DraftTarget.INVOICING:
        return deps.settings.INVOICING_EMAIL
    if target is DraftTarget.PAYMENTS:
        return deps.settings.PAYMENTS_EMAIL
    if target is DraftTarget.APPROVAL_OWNERS and invoice and invoice.approval_owner_email:
        return invoice.approval_owner_email
    return ticket.sender_email


def make_draft_node(deps: WorkflowDeps):
    async def draft(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()

        match_result = InvoiceMatchResult(state.get("match_result") or "not_found")
        invoice = None
        dump = state.get("invoice_dump")
        if dump:
            invoice = Invoice.model_validate(dump)
        is_overdue = bool(state.get("is_overdue"))
        is_near_due = bool(state.get("is_near_due"))
        target = pick_target(
            match_result=match_result,
            invoice=invoice,
            is_overdue=is_overdue,
            is_near_due=is_near_due,
        )
        if target is None:
            return {
                "should_stop": False,
                "ticket_id": str(ticket.id),
                "skip_draft": True,
                "draft_id": None,
                "audit_action": AuditAction.DRAFT.value,
                "audit_metadata": {"skipped": True, "match_result": match_result.value},
            }

        output = await deps.llm.generate(
            system_prompt=DRAFT_SYSTEM_PROMPT,
            user_prompt=f"Subject: {ticket.subject}\n\n{ticket.body}",
            output_schema=DraftOutput,
        )
        if not isinstance(output, DraftOutput):
            output = DraftOutput.model_validate(output)

        attach_proof = (
            invoice is not None
            and invoice.status is InvoiceStatus.PAID
            and bool(invoice.clearing_document)
        )
        saved = deps.drafts.save(
            ResponseDraft(
                ticket_id=ticket.id,
                target=target,
                to_email=_to_email(deps, target, ticket, invoice),
                generated_text=output.generated_text,
                attach_payment_proof=attach_proof,
            )
        )
        ticket.updated_at = datetime.now(UTC)
        deps.tickets.save_ticket(ticket)
        return {
            "should_stop": False,
            "ticket_id": str(ticket.id),
            "skip_draft": False,
            "draft_id": str(saved.id),
            "audit_action": AuditAction.DRAFT.value,
            "audit_metadata": {"target": target.value, "draft_id": str(saved.id)},
        }

    return draft
