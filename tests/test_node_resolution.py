"""Resolution matching (no Day-7 retry)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.adapters.mock_llm import MockLLMAdapter
from app.adapters.mock_sap import MockSAPAdapter
from app.domain.enums import DraftTarget, InvoiceMatchResult, InvoiceStage, InvoiceStatus, TicketStatus
from app.domain.models import Invoice, Ticket
from app.graph.match import match_invoices, normalize_reference
from app.graph.nodes.draft import pick_target
from app.graph.nodes.resolution import make_resolution_node
from settings import Settings
from tests.helpers import make_test_deps


def _ticket(**kwargs) -> Ticket:
    values = dict(
        thread_id="th-res",
        message_id=f"msg-{uuid4().hex[:8]}",
        sender_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Status?",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
        status=TicketStatus.OPEN,
    )
    values.update(kwargs)
    return Ticket(**values)


def _inv(**kwargs) -> Invoice:
    values = dict(
        invoice_ref="INV-2026-0001",
        supplier_name="ACME Supplies",
        amount=Decimal("1250.00"),
        stage=InvoiceStage.IN_APPROVAL,
        status=InvoiceStatus.PENDING,
        due_date=date(2026, 9, 15),
        approval_owner_email="ap-owner@company.com",
    )
    values.update(kwargs)
    return Invoice(**values)


def test_normalize_reference_strips_non_alnum():
    assert normalize_reference("inv-2026-0001") == "INV20260001"
    assert normalize_reference(None) == ""


def test_exact_match():
    settings = Settings()
    out = match_invoices(
        approval=[_inv()],
        posted=[],
        extracted_ref="INV-2026-0001",
        extracted_amount=1250.0,
        supplier_hint="ACME Supplies",
        settings=settings,
    )
    assert out.result is InvoiceMatchResult.MATCH
    assert out.method == "exact"
    assert out.requires_hitl is False


def test_both_sources_exact_is_multiple():
    out = match_invoices(
        approval=[_inv()],
        posted=[_inv(stage=InvoiceStage.POSTED, status=InvoiceStatus.PAID, clearing_document="CL-1")],
        extracted_ref="INV-2026-0001",
        extracted_amount=1250.0,
        supplier_hint="ACME Supplies",
        settings=Settings(),
    )
    assert out.result is InvoiceMatchResult.MULTIPLE
    assert out.requires_hitl is True


def test_fuzzy_match():
    out = match_invoices(
        approval=[_inv()],
        posted=[],
        extracted_ref="INV-2026-000l",
        extracted_amount=None,
        supplier_hint=None,
        settings=Settings(),
    )
    assert out.result is InvoiceMatchResult.MATCH
    assert out.method == "fuzzy"


def test_amount_and_supplier_match():
    out = match_invoices(
        approval=[_inv()],
        posted=[],
        extracted_ref="UNKNOWN-99",
        extracted_amount=1250.50,
        supplier_hint="ACME Supplies",
        settings=Settings(),
    )
    assert out.result is InvoiceMatchResult.MATCH
    assert out.method == "amount"


def test_not_found():
    out = match_invoices(
        approval=[_inv()],
        posted=[],
        extracted_ref="NOPE-1",
        extracted_amount=10.0,
        supplier_hint="Other Co",
        settings=Settings(),
    )
    assert out.result is InvoiceMatchResult.NOT_FOUND


def test_pick_target_table():
    assert pick_target(
        match_result=InvoiceMatchResult.NOT_FOUND,
        invoice=None,
        is_overdue=False,
        is_near_due=False,
    ) is DraftTarget.INVOICING
    assert (
        pick_target(
            match_result=InvoiceMatchResult.MULTIPLE,
            invoice=_inv(),
            is_overdue=False,
            is_near_due=False,
        )
        is None
    )
    overdue = _inv(due_date=date(2026, 8, 1))
    assert (
        pick_target(
            match_result=InvoiceMatchResult.MATCH,
            invoice=overdue,
            is_overdue=True,
            is_near_due=False,
        )
        is DraftTarget.APPROVAL_OWNERS
    )
    no_owner = _inv(approval_owner_email=None)
    assert (
        pick_target(
            match_result=InvoiceMatchResult.MATCH,
            invoice=no_owner,
            is_overdue=True,
            is_near_due=False,
        )
        is None
    )
    paid = _inv(
        stage=InvoiceStage.POSTED,
        status=InvoiceStatus.PAID,
        clearing_document="CL-1",
    )
    assert (
        pick_target(
            match_result=InvoiceMatchResult.MATCH,
            invoice=paid,
            is_overdue=False,
            is_near_due=False,
        )
        is DraftTarget.SENDER
    )
    blocked = _inv(stage=InvoiceStage.POSTED, status=InvoiceStatus.BLOCKED)
    assert (
        pick_target(
            match_result=InvoiceMatchResult.MATCH,
            invoice=blocked,
            is_overdue=False,
            is_near_due=False,
        )
        is DraftTarget.PAYMENTS
    )


@pytest.mark.asyncio
async def test_resolution_exact_fixture_and_paid_without_clearing_hitl():
    store_ticket = _ticket()
    deps = make_test_deps()
    deps.tickets.save_ticket(store_ticket)
    node = make_resolution_node(deps)
    update = await node(
        {
            "ticket_id": str(store_ticket.id),
            "extracted_ref": "INV-2026-0001",
            "extracted_amount": 1250.0,
        }
    )
    assert update["match_result"] == InvoiceMatchResult.MATCH.value
    assert update["match_method"] == "exact"
    assert update["requires_hitl"] is False

    paid = _inv(
        invoice_ref="INV-PAID-NC",
        stage=InvoiceStage.POSTED,
        status=InvoiceStatus.PAID,
        clearing_document=None,
    )
    deps.sap = MockSAPAdapter(approval=[], posted=[paid])
    other = _ticket()
    deps.tickets.save_ticket(other)
    update = await make_resolution_node(deps)(
        {
            "ticket_id": str(other.id),
            "extracted_ref": "INV-PAID-NC",
            "extracted_amount": 1250.0,
        }
    )
    assert update["requires_hitl"] is True


@pytest.mark.asyncio
async def test_resolution_vat_discrepancy_uses_llm_notes():
    ticket = _ticket()
    llm = MockLLMAdapter()
    llm.enqueue({"notes": "Extracted amount looks VAT-inclusive."})
    deps = make_test_deps(llm=llm)
    deps.tickets.save_ticket(ticket)
    update = await make_resolution_node(deps)(
        {
            "ticket_id": str(ticket.id),
            "extracted_ref": "INV-2026-0001",
            "extracted_amount": 1537.5,
        }
    )
    assert update["match_result"] == InvoiceMatchResult.VAT_DISCREPANCY.value
    assert update["requires_hitl"] is True
    assert "vat" in (update["vat_notes"] or "").lower()
