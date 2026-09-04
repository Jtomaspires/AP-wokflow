"""LangGraph state (inbound spine through HITL).

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
    match_result: str | None
    match_method: str | None
    invoice_ref: str | None
    invoice_dump: dict[str, Any] | None
    requires_hitl: bool
    is_overdue: bool
    is_near_due: bool
    vat_notes: str | None
    skip_draft: bool
    draft_id: str | None
    review_action: str | None
    operator_id: str | None
    audit_action: str | None
    audit_metadata: dict[str, Any]
    audit_confidence: float | None
