"""LangGraph state (ingest → routing; resolution is a Day-5 stub).

Do not put WorkflowDeps here — it does not serialize. Close deps in node factories.
"""

from typing import Any, TypedDict


class LabState(TypedDict, total=False):
    raw_payload: dict[str, Any]
    ticket_id: str | None
    should_stop: bool
    stop_reason: str | None
    route: str | None
    skip_identity: bool
    is_thread_continuation: bool
    extracted_ref: str | None
    extracted_amount: float | None
    intent: str | None
    sender_id: str | None
    spf_pass: bool | None
    dkim_pass: bool | None
    audit_action: str | None
    audit_metadata: dict[str, Any]
    audit_confidence: float | None
