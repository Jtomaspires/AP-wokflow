"""Resolution: SAP match ladder (no Day-7 retry)."""

from datetime import UTC, datetime

from pydantic import BaseModel

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, InvoiceMatchResult, InvoiceStatus
from app.graph.match import due_flags, looks_like_vat_gross, match_invoices
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState
from app.llm.prompts import VAT_SYSTEM_PROMPT


class VATReasoningOutput(BaseModel):
    notes: str


def make_resolution_node(deps: WorkflowDeps):
    async def resolution(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()

        extracted_ref = state.get("extracted_ref")
        extracted_amount = state.get("extracted_amount")
        sender = deps.senders.get_by_email(ticket.sender_email)
        supplier_hint = sender.company if sender else ticket.sender_email
        outcome = match_invoices(
            approval=deps.sap.get_approval_invoices(),
            posted=deps.sap.get_posted_invoices(),
            extracted_ref=extracted_ref,
            extracted_amount=extracted_amount,
            supplier_hint=supplier_hint,
            settings=deps.settings,
        )
        vat_notes = None
        result = outcome.result
        requires_hitl = outcome.requires_hitl
        invoice = outcome.invoice

        if (
            invoice is not None
            and result is InvoiceMatchResult.MATCH
            and looks_like_vat_gross(
                invoice=invoice,
                extracted_amount=extracted_amount,
                settings=deps.settings,
            )
        ):
            vat = await deps.llm.generate(
                system_prompt=VAT_SYSTEM_PROMPT,
                user_prompt=f"Extracted {extracted_amount} vs net {invoice.amount} VAT {deps.settings.VAT_RATE}",
                output_schema=VATReasoningOutput,
            )
            if not isinstance(vat, VATReasoningOutput):
                vat = VATReasoningOutput.model_validate(vat)
            vat_notes = vat.notes
            result = InvoiceMatchResult.VAT_DISCREPANCY
            requires_hitl = True

        if (
            invoice is not None
            and invoice.status is InvoiceStatus.PAID
            and not invoice.clearing_document
        ):
            requires_hitl = True

        overdue, near = due_flags(invoice, deps.settings)
        ticket.updated_at = datetime.now(UTC)
        deps.tickets.save_ticket(ticket)

        invoice_ref = invoice.invoice_ref if invoice else None
        return {
            "should_stop": False,
            "ticket_id": str(ticket.id),
            "stop_reason": None,
            "match_result": result.value,
            "match_method": outcome.method,
            "invoice_ref": invoice_ref,
            "requires_hitl": requires_hitl,
            "is_overdue": overdue,
            "is_near_due": near,
            "vat_notes": vat_notes,
            "invoice_dump": invoice.model_dump(mode="json") if invoice else None,
            "audit_action": AuditAction.RESOLVE.value,
            "audit_metadata": {
                "match_result": result.value,
                "match_method": outcome.method,
                "invoice_ref": invoice_ref,
            },
        }

    return resolution
