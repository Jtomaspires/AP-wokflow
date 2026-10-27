"""Draft: deterministic target, LLM writes generated_text only."""

from datetime import UTC, datetime

from pydantic import BaseModel

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, DraftTarget, InvoiceMatchResult, InvoiceStage, InvoiceStatus
from app.domain.models import Invoice, ResponseDraft
from app.graph.draft_guard import validate_draft
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState
from app.llm.prompts import DRAFT_SYSTEM_PROMPT, build_draft_user_prompt


class DraftOutput(BaseModel):
    generated_text: str


def pick_target(
    *,
    match_result: InvoiceMatchResult,
    invoice: Invoice | None,
    is_overdue: bool,
    is_near_due: bool,
) -> DraftTarget | None:
    # messy match — no auto draft
    if match_result in {
        InvoiceMatchResult.MULTIPLE,
        InvoiceMatchResult.TOO_MANY,
        InvoiceMatchResult.VAT_DISCREPANCY,
    }:
        return None
    # nothing in SAP — ask invoicing
    if match_result is InvoiceMatchResult.NOT_FOUND:
        return DraftTarget.INVOICING
    if invoice is None:
        return None
    if invoice.stage is InvoiceStage.IN_APPROVAL:
        # late and we know the approver — nudge them
        if (is_overdue or is_near_due) and invoice.approval_owner_email:
            return DraftTarget.APPROVAL_OWNERS
        # late, nobody to mail
        if is_overdue and not invoice.approval_owner_email:
            return None
        # still in approval, not urgent — reply to sender
        return DraftTarget.SENDER
    if invoice.stage is InvoiceStage.POSTED:
        # blocked, or pending and late — payments
        if invoice.status is InvoiceStatus.BLOCKED or (
            is_overdue and invoice.status is InvoiceStatus.PENDING
        ):
            return DraftTarget.PAYMENTS
        # pending / partial, not late yet
        if invoice.status in {InvoiceStatus.PENDING, InvoiceStatus.PARTIAL} and not is_overdue:
            return DraftTarget.SENDER
        # paid + clearing doc — sender gets the proof
        if invoice.status is InvoiceStatus.PAID and invoice.clearing_document:
            return DraftTarget.SENDER
        # paid but no proof — don't invent a reply
        if invoice.status is InvoiceStatus.PAID and not invoice.clearing_document:
            return None
        return DraftTarget.SENDER
    # anything else — sender
    return DraftTarget.SENDER


def _to_email(deps: WorkflowDeps, target: DraftTarget, ticket, invoice: Invoice | None) -> str:
    # inbox follows the target; fallback is the original sender
    if target is DraftTarget.INVOICING:
        return deps.settings.INVOICING_EMAIL
    if target is DraftTarget.PAYMENTS:
        return deps.settings.PAYMENTS_EMAIL
    if target is DraftTarget.APPROVAL_OWNERS and invoice and invoice.approval_owner_email:
        return invoice.approval_owner_email
    return ticket.sender_email


async def _generate(deps: WorkflowDeps, user_prompt: str) -> DraftOutput:
    output = await deps.llm.generate(
        system_prompt=DRAFT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        output_schema=DraftOutput,
    )
    if not isinstance(output, DraftOutput):
        return DraftOutput.model_validate(output)
    return output


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
        # no safe target — skip the llm, hitl still runs
        if target is None:
            return {
                "should_stop": False,
                "ticket_id": str(ticket.id),
                "skip_draft": True,
                "draft_id": None,
                "audit_action": AuditAction.DRAFT.value,
                "audit_metadata": {"skipped": True, "match_result": match_result.value},
            }

        to_email = _to_email(deps, target, ticket, invoice)
        user_prompt = build_draft_user_prompt(
            ticket=ticket,
            invoice=invoice,
            target=target,
            to_email=to_email,
            match_result=match_result,
            intent=ticket.intent,
        )
        output = await _generate(deps, user_prompt)
        violations = validate_draft(
            output.generated_text,
            target=target,
            invoice=invoice,
            match_result=match_result,
        )
        retried = False
        if violations:
            # one rewrite, then drop it
            retried = True
            codes = ", ".join(violations)
            output = await _generate(
                deps,
                user_prompt
                + f"\nYour previous draft was rejected for: {codes}. Rewrite it and fix exactly these problems.",
            )
            violations = validate_draft(
                output.generated_text,
                target=target,
                invoice=invoice,
                match_result=match_result,
            )
            if violations:
                return {
                    "should_stop": False,
                    "ticket_id": str(ticket.id),
                    "skip_draft": True,
                    "draft_id": None,
                    "audit_action": AuditAction.DRAFT.value,
                    "audit_metadata": {
                        "skipped": True,
                        "rejected": True,
                        "violations": violations,
                        "target": target.value,
                        "match_result": match_result.value,
                    },
                }

        # paid + clearing doc → attach the proof
        attach_proof = (
            invoice is not None
            and invoice.status is InvoiceStatus.PAID
            and bool(invoice.clearing_document)
        )
        saved = deps.drafts.save(
            ResponseDraft(
                ticket_id=ticket.id,
                target=target,
                to_email=to_email,
                generated_text=output.generated_text,
                attach_payment_proof=attach_proof,
            )
        )
        ticket.updated_at = datetime.now(UTC)
        deps.tickets.save_ticket(ticket)
        metadata = {"target": target.value, "draft_id": str(saved.id)}
        if retried:
            metadata["retried"] = True
        return {
            "should_stop": False,
            "ticket_id": str(ticket.id),
            "skip_draft": False,
            "draft_id": str(saved.id),
            "audit_action": AuditAction.DRAFT.value,
            "audit_metadata": metadata,
        }

    return draft
