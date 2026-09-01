"""LangGraph state for the lab (ingest → security → triage).

Do not put WorkflowDeps here — it does not serialize. Close deps in node factories.
"""

from typing import Any, TypedDict


class LabState(TypedDict, total=False):
    raw_payload: dict[str, Any]
    ticket_id: str | None
    should_stop: bool
    stop_reason: str | None
