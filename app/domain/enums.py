"""Domain enumerations (assistant parity)."""

from enum import Enum


class TicketStatus(str, Enum):
    OPEN = "open"
    AWAITING_HUMAN = "awaiting_human"
    AWAITING_SENDER_REPLY = "awaiting_sender_reply"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    QUARANTINED = "quarantined"
    DISCARDED = "discarded"
    DELEGATED = "delegated"


class Intent(str, Enum):
    PAYMENT_STATUS = "payment_status"
    DELAY_REASON = "delay_reason"
    FUTURE_TIMING = "future_timing"
    UNKNOWN = "unknown"


class SenderType(str, Enum):
    VENDOR = "vendor"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class InvoiceStage(str, Enum):
    IN_APPROVAL = "in_approval"
    POSTED = "posted"


class InvoiceStatus(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    PAID = "paid"
    PARTIAL = "partial"


class InvoiceMatchResult(str, Enum):
    MATCH = "match"
    NOT_FOUND = "not_found"
    MULTIPLE = "multiple"
    TOO_MANY = "too_many"
    VAT_DISCREPANCY = "vat_discrepancy"


class DraftTarget(str, Enum):
    SENDER = "sender"
    INVOICING = "invoicing"
    PAYMENTS = "payments"
    APPROVAL_OWNERS = "approval_owners"


class HumanReviewAction(str, Enum):
    APPROVE = "approve"
    APPROVE_EDIT = "approve_edit"
    ESCALATED_TO_EMAIL = "escalated_to_email"


class AuditAction(str, Enum):
    INGEST = "ingest"
    SECURITY = "security"
    QUARANTINE = "quarantine"
    PASS = "pass"
    TRIAGE = "triage"
    DISCARD = "discard"
    THREAD = "thread"
    INTENT = "intent"
    IDENTIFY = "identify"
    MINE = "mine"
    DELEGATE = "delegate"
    RESOLVE = "resolve"
    DRAFT = "draft"
    HITL = "hitl"
    SEND = "send"
    APPROVE = "approve"
    APPROVE_EDIT = "approve_edit"
    ESCALATE = "escalate"
