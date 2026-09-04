"""Golden eval against LangGraph ainvoke (not Launchpad workflow).

Thread continuations are not in this suite: each fixture is a new ticket
(unique message_id), matching the assistant harness default.
Resolution retry stays off (RESOLUTION_RETRY_ENABLED default False).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from app.graph.app import build_graph
from app.llm.judge import judge_draft
from app.ports.llm_port import LLMPort
from settings import Settings
from tests.helpers import make_test_deps

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "fixtures" / "emails"
DIMENSIONS = (
    "intent",
    "ticket_status",
    "invoice_resolution",
    "draft_target",
    "to_email",
    "attach_payment_proof",
    "human_action_needed",
)


class FixtureGuidedLLM(LLMPort):
    """LLMPort that returns structured fields from a fixture's expected block."""

    def __init__(self, expected: dict) -> None:
        self.expected = expected
        self.calls: list[str] = []

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[BaseModel],
    ) -> BaseModel:
        del system_prompt, user_prompt
        name = output_schema.__name__
        self.calls.append(name)
        exp = self.expected
        if name == "TriageOutput":
            payload = {
                "is_ap": exp.get("is_ap", True),
                "confidence": exp.get("triage_confidence", 0.95),
            }
        elif name == "IntentOutput":
            payload = {
                "intent": exp.get("intent") or "unknown",
                "confidence": exp.get("intent_confidence", 0.9),
                "language": exp.get("language", "en"),
                "extracted_ref": exp.get("extracted_ref"),
                "extracted_amount": exp.get("extracted_amount"),
            }
        elif name == "DraftOutput":
            payload = {"generated_text": exp.get("generated_text") or "Eval draft."}
        elif name == "VATReasoningOutput":
            payload = {"notes": exp.get("vat_notes") or "VAT-inclusive vs net mismatch."}
        else:
            raise RuntimeError(f"FixtureGuidedLLM has no mapping for {name}")
        return output_schema.model_validate(payload)


def load_fixtures(directory: Path | None = None) -> list[Path]:
    root = directory or FIXTURES_DIR
    return sorted(root.glob("*.json"))


def _actual(deps, final: dict) -> dict:
    ticket_id = final.get("ticket_id")
    ticket = deps.tickets.get_by_id(UUID(ticket_id)) if ticket_id else None
    draft = None
    if ticket is not None:
        drafts = deps.drafts.get_by_ticket_id(ticket.id)
        draft = drafts[-1] if drafts else None
    status = ticket.status.value if ticket else final.get("stop_reason")
    intent = ticket.intent.value if ticket is not None and ticket.intent else None
    return {
        "intent": intent,
        "ticket_status": status,
        "invoice_resolution": final.get("match_result"),
        "draft_target": draft.target.value if draft else None,
        "to_email": draft.to_email if draft else None,
        "attach_payment_proof": draft.attach_payment_proof if draft else None,
        "human_action_needed": status == "awaiting_human",
        "generated_text": draft.generated_text if draft else None,
    }


def score_dimensions(expected: dict, actual: dict) -> dict[str, bool]:
    return {name: actual.get(name) == expected.get(name) for name in DIMENSIONS}


async def run_fixture(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    expected = data["expected"]
    extra = data.get("settings") or {}
    settings = Settings(RESOLUTION_RETRY_ENABLED=False, **extra)
    deps = make_test_deps(
        settings=settings,
        llm=FixtureGuidedLLM(expected),
    )
    final = await build_graph(deps).ainvoke({"raw_payload": data["input"]})
    actual = _actual(deps, final)
    dimensions = score_dimensions(expected, actual)
    draft_ok = judge_draft(
        expected.get("generated_text"),
        actual.get("generated_text"),
        live=settings.EVAL_LIVE_LLM,
    )
    return {
        "id": data.get("id") or path.stem,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "actual": actual,
        "expected": {k: expected.get(k) for k in DIMENSIONS},
        "dimensions": dimensions,
        "draft_judge": draft_ok,
        "workflow_ok": all(dimensions.values()),
        "llm_calls": list(deps.llm.calls),
    }


async def run_all(directory: Path | None = None) -> dict:
    paths = load_fixtures(directory)
    rows = [await run_fixture(path) for path in paths]
    n = len(rows) or 1
    success = sum(1 for row in rows if row["workflow_ok"]) / n
    per_dim = {
        name: sum(1 for row in rows if row["dimensions"][name]) / n for name in DIMENSIONS
    }
    return {
        "success": success,
        "threshold": Settings().WORKFLOW_SUCCESS_THRESHOLD,
        "count": len(rows),
        "per_dimension": per_dim,
        "results": rows,
        "graph": "langgraph",
        "retry_enabled": False,
    }


def run_all_sync(directory: Path | None = None) -> dict:
    return asyncio.run(run_all(directory))
