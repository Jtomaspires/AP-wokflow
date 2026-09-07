"""Resolution: SAP match ladder, optional one-shot retry inside this node."""

from datetime import UTC, datetime

from pydantic import BaseModel

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, InvoiceMatchResult, InvoiceStatus
from app.graph.match import (
    due_flags,
    looks_like_vat_gross,
    match_invoices,
    should_retry_match,
    widened_match_settings,
)
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
        kwargs = dict(
            approval=deps.sap.get_approval_invoices(),
            posted=deps.sap.get_posted_invoices(),
            extracted_ref=extracted_ref,
            extracted_amount=extracted_amount,
            supplier_hint=supplier_hint,
        )
        first = match_invoices(settings=deps.settings, **kwargs)
        outcome = first
        retry_n = 0
        retry_meta: dict = {}
        if should_retry_match(first, deps.settings, retry_n=0):
            wide = widened_match_settings(deps.settings)
            second = match_invoices(
                settings=wide,
                fuzzy_cutoff=deps.settings.RESOLUTION_RETRY_FUZZY_FLOOR,
                **kwargs,
            )
            retry_n = 1
            retry_meta = {
                "retry_n": retry_n,
                "previous_result": first.result.value,
                "previous_confidence": first.confidence,
                "previous_method": first.method,
                "old_tolerance_abs": deps.settings.MATCH_VALUE_TOLERANCE_ABS,
                "new_tolerance_abs": wide.MATCH_VALUE_TOLERANCE_ABS,
                "old_fuzzy_cutoff": deps.settings.MATCH_FUZZY_CUTOFF,
                "new_fuzzy_cutoff": deps.settings.RESOLUTION_RETRY_FUZZY_FLOOR,
            }
            outcome = second

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
        audit_metadata = {
            "match_result": result.value,
            "match_method": outcome.method,
            "invoice_ref": invoice_ref,
            "match_confidence": outcome.confidence,
            "retry_n": retry_n,
            **retry_meta,
        }
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
            "audit_metadata": audit_metadata,
        }

    return resolution
