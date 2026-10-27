"""Draft node: target, prompt, one retry, then fail closed."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel

from app.domain.enums import Intent, InvoiceMatchResult, InvoiceStage, InvoiceStatus
from app.domain.models import Invoice, Ticket
from app.graph.nodes.draft import make_draft_node
from tests.helpers import make_test_deps

_CLEAN = "Please locate invoice INV-NOPE. We have no matching record."
_THANKS = "Thank you for your email about INV-NOPE"


class _RecordingLLM:
    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self.user_prompts: list[str] = []

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[BaseModel],
    ) -> BaseModel:
        del system_prompt
        self.user_prompts.append(user_prompt)
        return output_schema.model_validate({"generated_text": self._outputs.pop(0)})


def _ticket() -> Ticket:
    return Ticket(
        thread_id="t-draft",
        message_id="m-draft",
        sender_email="billing@acme-supplies.com",
        subject="Where is INV-NOPE?",
        body="Please confirm invoice INV-NOPE.",
        received_at=datetime(2026, 9, 4, tzinfo=UTC),
        intent=Intent.PAYMENT_STATUS,
    )


def _paid(**overrides) -> Invoice:
    data = dict(
        invoice_ref="INV-2026-0002",
        supplier_name="ACME Supplies",
        amount=Decimal("980.50"),
        stage=InvoiceStage.POSTED,
        status=InvoiceStatus.PAID,
        clearing_document="CL-9001",
    )
    data.update(overrides)
    return Invoice(**data)


@pytest.mark.asyncio
async def test_not_found_saves_internal_note():
    llm = _RecordingLLM([_CLEAN])
    deps = make_test_deps(llm=llm)
    ticket = deps.tickets.save_ticket(_ticket())

    update = await make_draft_node(deps)(
        {"ticket_id": str(ticket.id), "match_result": InvoiceMatchResult.NOT_FOUND.value}
    )

    drafts = deps.drafts.get_by_ticket_id(ticket.id)
    assert update["skip_draft"] is False
    assert drafts[-1].to_email == deps.settings.INVOICING_EMAIL
    assert "Do not thank them" in llm.user_prompts[0]


@pytest.mark.asyncio
async def test_internal_thanks_is_retried_then_saved():
    llm = _RecordingLLM([_THANKS, _CLEAN])
    deps = make_test_deps(llm=llm)
    ticket = deps.tickets.save_ticket(_ticket())

    update = await make_draft_node(deps)(
        {"ticket_id": str(ticket.id), "match_result": InvoiceMatchResult.NOT_FOUND.value}
    )

    assert len(llm.user_prompts) == 2
    assert "rejected for: internal_addresses_supplier" in llm.user_prompts[1]
    assert update["audit_metadata"]["retried"] is True
    assert deps.drafts.get_by_ticket_id(ticket.id)[-1].generated_text == _CLEAN


@pytest.mark.asyncio
async def test_internal_thanks_twice_drops_the_draft():
    llm = _RecordingLLM([_THANKS, _THANKS])
    deps = make_test_deps(llm=llm)
    ticket = deps.tickets.save_ticket(_ticket())

    update = await make_draft_node(deps)(
        {"ticket_id": str(ticket.id), "match_result": InvoiceMatchResult.NOT_FOUND.value}
    )

    assert update["skip_draft"] is True
    assert update["draft_id"] is None
    assert update["audit_metadata"]["rejected"] is True
    assert "internal_addresses_supplier" in update["audit_metadata"]["violations"]
    assert deps.drafts.get_by_ticket_id(ticket.id) == []


@pytest.mark.asyncio
async def test_paid_without_clearing_skips_llm():
    llm = _RecordingLLM([])
    deps = make_test_deps(llm=llm)
    ticket = deps.tickets.save_ticket(_ticket())
    invoice = _paid(clearing_document=None)

    update = await make_draft_node(deps)(
        {
            "ticket_id": str(ticket.id),
            "match_result": InvoiceMatchResult.MATCH.value,
            "invoice_dump": invoice.model_dump(mode="json"),
        }
    )

    assert llm.user_prompts == []
    assert update["skip_draft"] is True
    assert deps.drafts.get_by_ticket_id(ticket.id) == []


@pytest.mark.asyncio
async def test_paid_with_clearing_attaches_proof():
    llm = _RecordingLLM(["Invoice INV-2026-0002 is settled. Clearing document CL-9001."])
    deps = make_test_deps(llm=llm)
    ticket = deps.tickets.save_ticket(_ticket())

    update = await make_draft_node(deps)(
        {
            "ticket_id": str(ticket.id),
            "match_result": InvoiceMatchResult.MATCH.value,
            "invoice_dump": _paid().model_dump(mode="json"),
        }
    )

    drafts = deps.drafts.get_by_ticket_id(ticket.id)
    assert update["skip_draft"] is False
    assert drafts[-1].attach_payment_proof is True
