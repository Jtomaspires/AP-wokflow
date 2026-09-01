"""Triage node: first LLM call — is this an AP email?

Uses ``LLMPort`` + ``TriageOutput``. Not AP with confidence at or above
``TRIAGE_DISCARD_MIN_CONFIDENCE`` → ``discarded`` and stop. Otherwise the
ticket stays OPEN (including low-confidence non-AP). Async so the compiled
graph will use ``ainvoke``.
"""

from datetime import UTC, datetime
from uuid import UUID

from app.domain.deps import WorkflowDeps
from app.domain.enums import TicketStatus
from app.domain.schemas import TriageOutput
from app.graph.state import LabState

_SYSTEM_PROMPT = (
    "You classify inbound email for accounts payable. "
    "Set is_ap true if the message is about invoices, billing, or payment. "
    "Set confidence between 0 and 1."
)


def make_triage_node(deps: WorkflowDeps):
    async def triage(state: LabState) -> dict:
        raw_id = state.get("ticket_id")
        if not raw_id:
            return {"should_stop": True, "stop_reason": "missing_ticket"}

        ticket = deps.tickets.get_by_id(UUID(raw_id))
        if ticket is None:
            return {"should_stop": True, "stop_reason": "missing_ticket"}

        output = await deps.llm.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=f"Subject: {ticket.subject}\n\n{ticket.body}",
            output_schema=TriageOutput,
        )
        if not isinstance(output, TriageOutput):
            output = TriageOutput.model_validate(output)

        ticket.is_ap = output.is_ap
        ticket.updated_at = datetime.now(UTC)

        discard = (
            not output.is_ap
            and output.confidence >= deps.settings.TRIAGE_DISCARD_MIN_CONFIDENCE
        )
        if discard:
            ticket.status = TicketStatus.DISCARDED
            saved = deps.tickets.save_ticket(ticket)
            return {
                "should_stop": True,
                "ticket_id": str(saved.id),
                "stop_reason": "discarded",
            }

        saved = deps.tickets.save_ticket(ticket)
        return {
            "should_stop": False,
            "ticket_id": str(saved.id),
            "stop_reason": None,
        }

    return triage
