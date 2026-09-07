"""Intent: LLM classify + extract; skip sender/routing when unknown/low conf."""

from datetime import UTC, datetime

from pydantic import BaseModel

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, Intent
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState

_SYSTEM_PROMPT = (
    "Classify AP email intent as payment_status, delay_reason, future_timing, "
    "or unknown. Extract invoice ref, amount, and language when possible."
)


class IntentOutput(BaseModel):
    intent: Intent
    confidence: float
    language: str | None = None
    extracted_ref: str | None = None
    extracted_amount: float | None = None


def make_intent_node(deps: WorkflowDeps):
    async def intent(state: LabState) -> dict:
        ticket = load_ticket(deps, state)
        if ticket is None:
            return missing_ticket()

        output = await deps.llm.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=f"Subject: {ticket.subject}\n\n{ticket.body}",
            output_schema=IntentOutput,
        )
        if not isinstance(output, IntentOutput):
            output = IntentOutput.model_validate(output)

        ticket.intent = output.intent
        ticket.language = output.language
        ticket.confidence = output.confidence
        ticket.updated_at = datetime.now(UTC)
        saved = deps.tickets.save_ticket(ticket)

        skip = (
            output.intent is Intent.UNKNOWN
            or output.confidence < deps.settings.INTENT_MIN_CONFIDENCE
        )
        return {
            "should_stop": False,
            "ticket_id": str(saved.id),
            "stop_reason": None,
            "intent": output.intent.value,
            "extracted_ref": output.extracted_ref,
            "extracted_amount": output.extracted_amount,
            "skip_identity": skip,
            "route": "resolution" if skip else "sender",
            "audit_action": AuditAction.INTENT.value,
            "audit_confidence": output.confidence,
            "audit_metadata": {"skip_identity": skip, "intent": output.intent.value},
        }

    return intent
