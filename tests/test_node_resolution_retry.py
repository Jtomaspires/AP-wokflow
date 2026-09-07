"""Day-7 resolution retry (inside the node, off by default)."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.adapters.mock_sap import MockSAPAdapter
from app.domain.enums import InvoiceMatchResult, InvoiceStage, InvoiceStatus, TicketStatus
from app.domain.models import Invoice, Ticket
from app.graph.match import match_invoices, should_retry_match, widened_match_settings
from app.graph.nodes.resolution import make_resolution_node
from settings import Settings
from tests.helpers import make_test_deps


def _ticket() -> Ticket:
    return Ticket(
        thread_id="th-retry",
        message_id=f"msg-{uuid4().hex[:8]}",
        sender_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Status?",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
        status=TicketStatus.OPEN,
    )


def _inv(**kwargs) -> Invoice:
    values = dict(
        invoice_ref="INV-WIDE",
        supplier_name="ACME Supplies",
        amount=Decimal("1250.00"),
        stage=InvoiceStage.IN_APPROVAL,
        status=InvoiceStatus.PENDING,
    )
    values.update(kwargs)
    return Invoice(**values)


def test_should_not_retry_when_disabled():
    settings = Settings(RESOLUTION_RETRY_ENABLED=False)
    miss = match_invoices(
        approval=[_inv()],
        posted=[],
        extracted_ref="NOPE",
        extracted_amount=1280.0,
        supplier_hint="ACME Supplies",
        settings=settings,
    )
    assert miss.result is InvoiceMatchResult.NOT_FOUND
    assert should_retry_match(miss, settings, retry_n=0) is False


def test_cap_blocks_second_retry():
    settings = Settings(RESOLUTION_RETRY_ENABLED=True, RESOLUTION_RETRY_MAX=1)
    miss = match_invoices(
        approval=[_inv()],
        posted=[],
        extracted_ref="NOPE",
        extracted_amount=10.0,
        supplier_hint="Other",
        settings=settings,
    )
    assert should_retry_match(miss, settings, retry_n=0) is True
    assert should_retry_match(miss, settings, retry_n=1) is False


@pytest.mark.asyncio
async def test_retry_amount_tolerance_finds_unique_match():
    ticket = _ticket()
    settings = Settings(
        RESOLUTION_RETRY_ENABLED=True,
        MATCH_VALUE_TOLERANCE_ABS=1.0,
        MATCH_VALUE_TOLERANCE_PCT=0.02,
        RESOLUTION_RETRY_TOLERANCE_MULTIPLIER=4.0,
        SENDER_DOMAIN_WHITELIST="acme-supplies.com",
    )
    deps = make_test_deps(
        settings=settings,
        sap=MockSAPAdapter(approval=[_inv()], posted=[]),
    )
    deps.tickets.save_ticket(ticket)
    update = await make_resolution_node(deps)(
        {
            "ticket_id": str(ticket.id),
            "extracted_ref": "UNKNOWN-99",
            "extracted_amount": 1280.0,
        }
    )
    assert update["match_result"] == InvoiceMatchResult.MATCH.value
    assert update["match_method"] == "amount"
    assert update["requires_hitl"] is False
    assert update["audit_metadata"]["retry_n"] == 1
    assert update["audit_metadata"]["previous_result"] == InvoiceMatchResult.NOT_FOUND.value
    first = match_invoices(
        approval=[_inv()],
        posted=[],
        extracted_ref="UNKNOWN-99",
        extracted_amount=1280.0,
        supplier_hint="ACME Supplies",
        settings=Settings(MATCH_VALUE_TOLERANCE_ABS=1.0, MATCH_VALUE_TOLERANCE_PCT=0.02),
    )
    assert first.result is InvoiceMatchResult.NOT_FOUND


@pytest.mark.asyncio
async def test_retry_still_requires_hitl_when_unmatched():
    ticket = _ticket()
    settings = Settings(RESOLUTION_RETRY_ENABLED=True)
    deps = make_test_deps(
        settings=settings,
        sap=MockSAPAdapter(approval=[_inv()], posted=[]),
    )
    deps.tickets.save_ticket(ticket)
    update = await make_resolution_node(deps)(
        {
            "ticket_id": str(ticket.id),
            "extracted_ref": "NOPE-1",
            "extracted_amount": 10.0,
        }
    )
    assert update["match_result"] == InvoiceMatchResult.NOT_FOUND.value
    assert update["audit_metadata"]["retry_n"] == 1
    assert update["audit_metadata"]["previous_result"] == InvoiceMatchResult.NOT_FOUND.value


def test_widened_settings_do_not_mutate_original():
    settings = Settings(MATCH_VALUE_TOLERANCE_ABS=1.0)
    wide = widened_match_settings(settings)
    assert settings.MATCH_VALUE_TOLERANCE_ABS == 1.0
    assert wide.MATCH_VALUE_TOLERANCE_ABS == 4.0
    assert wide.MATCH_FUZZY_CUTOFF == settings.RESOLUTION_RETRY_FUZZY_FLOOR
