"""LLM system prompts (assistant parity, shortened)."""

from __future__ import annotations

from app.domain.enums import DraftTarget, Intent, InvoiceMatchResult
from app.domain.models import Invoice, Ticket

DRAFT_SYSTEM_PROMPT = (
    "You write short professional accounts-payable emails. "
    "When the user prompt asks for an internal email, write only to that team. "
    "Do not thank or address the supplier. "
    "Do not invent invoice numbers, amounts, or payment dates. "
    "Only state that an invoice is paid when Clearing document is yes. "
    "Return only generated_text."
)


def build_draft_user_prompt(
    *,
    ticket: Ticket,
    invoice: Invoice | None,
    target: DraftTarget,
    to_email: str,
    match_result: InvoiceMatchResult,
    intent: Intent | None,
) -> str:
    lines = [
        f"Intent: {intent.value if intent else 'unknown'}",
        f"Match result: {match_result.value}",
    ]
    if invoice is not None:
        lines += [
            f"Invoice ref: {invoice.invoice_ref}",
            f"Amount: {invoice.amount} {invoice.currency}",
            f"Stage: {invoice.stage.value}",
            f"Status: {invoice.status.value if invoice.status else 'unknown'}",
            f"Due date: {invoice.due_date or 'unknown'}",
            f"Clearing document: {'yes' if invoice.clearing_document else 'no'}",
            f"Payment date: {invoice.payment_date or 'unknown'}",
            f"Blocking reason: {invoice.payment_blocking_reason or 'none'}",
        ]
    lines.append("")
    if target is DraftTarget.SENDER:
        lines += [
            f"Reply to: {to_email}",
            f"Original message from {ticket.sender_email}:",
            f"Subject: {ticket.subject}",
            "",
            ticket.body,
        ]
    else:
        lines += [
            f"Write an internal email to: {to_email} ({target.value} team)",
            f"The supplier {ticket.sender_email} sent this request:",
            f"Subject: {ticket.subject}",
            "",
            ticket.body,
            "",
            f"Ask the {target.value} team to locate or unblock the invoice.",
            "Do not address the supplier directly. Do not thank them.",
        ]
    return "\n".join(lines)

VAT_SYSTEM_PROMPT = (
    "The extracted amount looks like a VAT-inclusive gross vs the SAP net. "
    "Write one short operator note. Do not decide the match."
)
