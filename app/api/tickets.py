"""Ticket list/detail payloads (ticket + sender + draft + invoice + audit)."""

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction
from app.domain.models import Ticket


def ticket_json(ticket: Ticket) -> dict:
    return ticket.model_dump(mode="json")


def ticket_detail(deps: WorkflowDeps, ticket: Ticket) -> dict:
    sender = deps.senders.get_by_email(ticket.sender_email)
    drafts = deps.drafts.get_by_ticket_id(ticket.id)
    draft = drafts[-1] if drafts else None
    audit = deps.audit.get_by_ticket_id(ticket.id)
    invoice_ref = None
    for entry in reversed(audit):
        if entry.action is AuditAction.RESOLVE:
            invoice_ref = (entry.metadata or {}).get("invoice_ref")
            break
    invoice = None
    if invoice_ref:
        for inv in deps.sap.get_approval_invoices() + deps.sap.get_posted_invoices():
            if inv.invoice_ref == invoice_ref:
                invoice = inv
                break
    body = ticket_json(ticket)
    body["sender"] = sender.model_dump(mode="json") if sender else None
    body["draft"] = draft.model_dump(mode="json") if draft else None
    body["invoice"] = invoice.model_dump(mode="json") if invoice else None
    body["audit"] = [
        {"node": e.node, "action": e.action.value, "metadata": e.metadata}
        for e in audit
    ]
    return body
