"""Intent: LLM classify + extract; skip sender/routing when unknown/low conf."""

from datetime import UTC, datetime

from pydantic import BaseModel

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction, Intent
from app.graph.nodes._ticket import load_ticket, missing_ticket
from app.graph.state import LabState

_SYSTEM_PROMPT = (
    "Classify AP email intent as payment_status, delay_reason, future_timing, "
    "or unknown. Extract invoice ref, amount, and language when possible. "
    "Set extraction_confidence between 0 and 1 for how sure the ref and amount are: "
    "1.0 exact, 0.7 likely, 0.3 ambiguous, 0.0 not extracted."
)


class IntentOutput(BaseModel):
    intent: Intent
    confidence: float
    language: str | None = None
    extracted_ref: str | None = None
    extracted_amount: float | None = None
    extraction_confidence: float = 1.0


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

        # bad spf/dkim knocks the score down
        penalty = state.get("spf_dkim_penalty") or 0.0
        adjusted_confidence = max(0.0, output.confidence - penalty)
        ticket.intent = output.intent
        ticket.language = output.language
        ticket.confidence = adjusted_confidence
        ticket.updated_at = datetime.now(UTC)
        saved = deps.tickets.save_ticket(ticket)

        # unknown or too unsure — skip sender + routing, straight to match
        skip = (
            output.intent is Intent.UNKNOWN
            or adjusted_confidence < deps.settings.INTENT_MIN_CONFIDENCE
        )
        return {
            "should_stop": False,
            "ticket_id": str(saved.id),
            "stop_reason": None,
            "intent": output.intent.value,
            "extracted_ref": output.extracted_ref,
            "extracted_amount": output.extracted_amount,
            "extraction_confidence": output.extraction_confidence,
            "skip_identity": skip,
            "route": "resolution" if skip else "sender",
            "audit_action": AuditAction.INTENT.value,
            "audit_confidence": adjusted_confidence,
            "audit_metadata": {
                "skip_identity": skip,
                "intent": output.intent.value,
                "llm_confidence": output.confidence,
                "spf_dkim_penalty": penalty,
                "extraction_confidence": output.extraction_confidence,
            },
        }

    return intent
