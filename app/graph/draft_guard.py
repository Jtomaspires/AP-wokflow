"""Reject draft text that thanks a supplier or claims payment without proof."""

from app.domain.enums import DraftTarget, InvoiceMatchResult
from app.domain.models import Invoice

_SUPPLIER_PHRASES = (
    "thank you",
    "thanks for",
    "dear supplier",
    "we have received your",
    "your invoice",
)

_PAID_PHRASES = (
    "has been paid",
    "was paid",
    "fully paid",
)


def validate_draft(
    text: str,
    *,
    target: DraftTarget,
    invoice: Invoice | None,
    match_result: InvoiceMatchResult,
) -> list[str]:
    # caller passes the match; these rules do not branch on it
    del match_result
    lowered = text.lower()
    violations: list[str] = []
    if target is not DraftTarget.SENDER and any(phrase in lowered for phrase in _SUPPLIER_PHRASES):
        violations.append("internal_addresses_supplier")
    if any(phrase in lowered for phrase in _PAID_PHRASES) and (
        invoice is None or not invoice.clearing_document
    ):
        violations.append("paid_without_clearing")
    if invoice is not None and invoice.invoice_ref not in text:
        violations.append("missing_invoice_ref")
    if not text.strip():
        violations.append("empty")
    return violations
