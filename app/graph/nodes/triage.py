"""Triage: AP vs discard; AP continues to intent."""

from datetime import UTC, datetime

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, TicketStatus
from app.domain.schemas import TriageOutput
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState

_SYSTEM_PROMPT = (
    "You classify inbound email for accounts payable. "
    "Set is_ap true if the message is about invoices, billing, or payment. "
    "Set confidence between 0 and 1."
)


def make_triage_node(deps: WorkflowDeps):
    async def triage(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()

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
                "route": "end",
                "audit_action": AuditAction.DISCARD.value,
                "audit_confidence": output.confidence,
                "audit_metadata": {"is_ap": False},
            }

        saved = deps.tickets.save_ticket(ticket)
        return {
            "should_stop": False,
            "ticket_id": str(saved.id),
            "stop_reason": None,
            "route": "intent",
            "audit_action": AuditAction.PASS.value,
            "audit_confidence": output.confidence,
            "audit_metadata": {"is_ap": True},
        }

    return triage
