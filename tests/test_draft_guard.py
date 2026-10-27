"""Pure draft-text checks. No LLM, no I/O."""

from decimal import Decimal

from app.domain.enums import DraftTarget, InvoiceMatchResult, InvoiceStage, InvoiceStatus
from app.domain.models import Invoice
from app.graph.draft_guard import validate_draft


def _invoice(**overrides) -> Invoice:
    data = dict(
        invoice_ref="INV-1",
        supplier_name="ACME",
        amount=Decimal("10"),
        stage=InvoiceStage.POSTED,
        status=InvoiceStatus.PENDING,
        clearing_document="CL-1",
    )
    data.update(overrides)
    return Invoice(**data)


def test_internal_addresses_supplier():
    codes = validate_draft(
        "Thank you. Invoice INV-1 is in review.",
        target=DraftTarget.INVOICING,
        invoice=_invoice(),
        match_result=InvoiceMatchResult.NOT_FOUND,
    )
    assert codes == ["internal_addresses_supplier"]


def test_paid_without_clearing():
    codes = validate_draft(
        "Invoice INV-1 has been paid.",
        target=DraftTarget.SENDER,
        invoice=_invoice(clearing_document=None, status=InvoiceStatus.PAID),
        match_result=InvoiceMatchResult.MATCH,
    )
    assert codes == ["paid_without_clearing"]


def test_missing_invoice_ref():
    codes = validate_draft(
        "We are still reviewing it.",
        target=DraftTarget.SENDER,
        invoice=_invoice(),
        match_result=InvoiceMatchResult.MATCH,
    )
    assert codes == ["missing_invoice_ref"]


def test_empty():
    codes = validate_draft(
        "   ",
        target=DraftTarget.SENDER,
        invoice=None,
        match_result=InvoiceMatchResult.NOT_FOUND,
    )
    assert codes == ["empty"]


def test_valid_supplier_reply():
    codes = validate_draft(
        "Thank you. Invoice INV-1 is still in approval.",
        target=DraftTarget.SENDER,
        invoice=_invoice(
            stage=InvoiceStage.IN_APPROVAL,
            status=InvoiceStatus.PENDING,
            clearing_document=None,
        ),
        match_result=InvoiceMatchResult.MATCH,
    )
    assert codes == []


def test_valid_internal_note():
    codes = validate_draft(
        "Please locate invoice INV-1. We have no matching record.",
        target=DraftTarget.INVOICING,
        invoice=None,
        match_result=InvoiceMatchResult.NOT_FOUND,
    )
    assert codes == []


def test_supplier_phrase_is_case_insensitive():
    codes = validate_draft(
        "THANK YOU. Invoice INV-1 is in review.",
        target=DraftTarget.PAYMENTS,
        invoice=_invoice(),
        match_result=InvoiceMatchResult.MATCH,
    )
    assert codes == ["internal_addresses_supplier"]


def test_negated_paid_claim_without_clearing_is_valid():
    codes = validate_draft(
        "This invoice INV-1 has not been paid yet",
        target=DraftTarget.SENDER,
        invoice=_invoice(clearing_document=None),
        match_result=InvoiceMatchResult.MATCH,
    )
    assert codes == []
