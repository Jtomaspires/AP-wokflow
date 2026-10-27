"""Draft user prompt carries the invoice facts the model may state."""

from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.enums import DraftTarget, Intent, InvoiceMatchResult, InvoiceStage, InvoiceStatus
from app.domain.models import Invoice, Ticket
from app.llm.prompts import build_draft_user_prompt


def _ticket() -> Ticket:
    return Ticket(
        thread_id="t1",
        message_id="m1",
        sender_email="billing@acme-supplies.com",
        subject="Was INV-2026-0002 paid?",
        body="Need proof for INV-2026-0002 / 980.50 EUR.",
        received_at=datetime(2026, 9, 4, tzinfo=UTC),
    )


def _invoice(**overrides) -> Invoice:
    data = dict(
        invoice_ref="INV-2026-0002",
        supplier_name="ACME Supplies",
        amount=Decimal("980.50"),
        stage=InvoiceStage.POSTED,
        status=InvoiceStatus.PAID,
        due_date=date(2026, 8, 1),
        clearing_document="CL-9001",
        payment_date=date(2026, 8, 5),
    )
    data.update(overrides)
    return Invoice(**data)


def _prompt(invoice: Invoice | None) -> str:
    return build_draft_user_prompt(
        ticket=_ticket(),
        invoice=invoice,
        target=DraftTarget.SENDER,
        to_email="billing@acme-supplies.com",
        match_result=InvoiceMatchResult.MATCH,
        intent=Intent.PAYMENT_STATUS,
    )


def test_prompt_contains_invoice_facts_and_original_body():
    prompt = _prompt(_invoice())
    assert "Invoice ref: INV-2026-0002" in prompt
    assert "Amount: 980.50 EUR" in prompt
    assert "Status: paid" in prompt
    assert "Clearing document: yes" in prompt
    assert "Reply to: billing@acme-supplies.com" in prompt
    assert "Original message from billing@acme-supplies.com:" in prompt
    assert "Need proof for INV-2026-0002 / 980.50 EUR." in prompt


def test_prompt_flags_missing_clearing_document():
    prompt = _prompt(_invoice(clearing_document=None))
    assert "Clearing document: no" in prompt


def test_prompt_without_invoice_has_no_invoice_lines():
    prompt = _prompt(None)
    assert "Invoice ref" not in prompt
    assert "Match result: match" in prompt


def test_internal_target_is_not_a_supplier_reply():
    prompt = build_draft_user_prompt(
        ticket=_ticket(),
        invoice=None,
        target=DraftTarget.INVOICING,
        to_email="invoicing@company.com",
        match_result=InvoiceMatchResult.NOT_FOUND,
        intent=Intent.PAYMENT_STATUS,
    )
    assert "Write an internal email to: invoicing@company.com (invoicing team)" in prompt
    assert "The supplier billing@acme-supplies.com sent this request:" in prompt
    assert "Do not address the supplier directly. Do not thank them." in prompt
    assert "Reply to:" not in prompt


def test_prompt_is_deterministic():
    assert _prompt(_invoice()) == _prompt(_invoice())
