"""Invoice reference matching (exact → fuzzy → amount+supplier)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher

from app.domain.enums import InvoiceMatchResult
from app.domain.models import Invoice
from settings import Settings


def normalize_reference(ref: str | None) -> str:
    if not ref:
        return ""
    return "".join(ch for ch in ref.upper() if ch.isalnum())


def _fuzzy(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


def _amounts_close(left: Decimal, right: Decimal, settings: Settings) -> bool:
    diff = abs(left - right)
    cap = max(
        Decimal(str(settings.MATCH_VALUE_TOLERANCE_ABS)),
        Decimal(str(settings.MATCH_VALUE_TOLERANCE_PCT)) * max(left, right),
    )
    return diff <= cap


def _supplier_close(left: str, right: str) -> bool:
    a, b = left.lower().strip(), right.lower().strip()
    if not a or not b:
        return False
    return a in b or b in a or _fuzzy(a, b) >= 0.8


@dataclass
class MatchOutcome:
    result: InvoiceMatchResult
    method: str | None
    invoice: Invoice | None
    requires_hitl: bool
    vat_notes: str | None = None
    confidence: float = 0.0


def match_invoices(
    *,
    approval: list[Invoice],
    posted: list[Invoice],
    extracted_ref: str | None,
    extracted_amount: float | None,
    supplier_hint: str | None,
    settings: Settings,
    fuzzy_cutoff: float | None = None,
) -> MatchOutcome:
    pool = list(approval) + list(posted)
    needle = normalize_reference(extracted_ref)
    cutoff = settings.MATCH_FUZZY_CUTOFF if fuzzy_cutoff is None else fuzzy_cutoff

    exact_app = [i for i in approval if needle and normalize_reference(i.invoice_ref) == needle]
    exact_post = [i for i in posted if needle and normalize_reference(i.invoice_ref) == needle]
    exact = exact_app + exact_post
    if len(exact_app) >= 1 and len(exact_post) >= 1:
        return MatchOutcome(InvoiceMatchResult.MULTIPLE, "exact", None, True, confidence=0.3)
    if len(exact) > 1:
        return MatchOutcome(InvoiceMatchResult.TOO_MANY, "exact", None, True, confidence=0.2)
    if len(exact) == 1:
        return MatchOutcome(InvoiceMatchResult.MATCH, "exact", exact[0], False, confidence=1.0)

    if needle:
        scored = [
            (inv, _fuzzy(normalize_reference(inv.invoice_ref), needle))
            for inv in pool
        ]
        fuzzy_hits = [(inv, score) for inv, score in scored if score >= cutoff]
        if len(fuzzy_hits) > 3:
            return MatchOutcome(InvoiceMatchResult.TOO_MANY, "fuzzy", None, True, confidence=0.2)
        if len(fuzzy_hits) > 1:
            return MatchOutcome(InvoiceMatchResult.MULTIPLE, "fuzzy", None, True, confidence=0.3)
        if len(fuzzy_hits) == 1:
            inv, score = fuzzy_hits[0]
            return MatchOutcome(InvoiceMatchResult.MATCH, "fuzzy", inv, False, confidence=score)

    amount = Decimal(str(extracted_amount)) if extracted_amount is not None else None
    if amount is not None and supplier_hint:
        amount_hits = [
            inv
            for inv in pool
            if _amounts_close(inv.amount, amount, settings)
            and _supplier_close(inv.supplier_name, supplier_hint)
        ]
        if len(amount_hits) > 1:
            return MatchOutcome(InvoiceMatchResult.MULTIPLE, "amount", None, True, confidence=0.3)
        if len(amount_hits) == 1:
            return MatchOutcome(InvoiceMatchResult.MATCH, "amount", amount_hits[0], False, confidence=0.8)

    return MatchOutcome(InvoiceMatchResult.NOT_FOUND, None, None, False, confidence=0.0)


def due_flags(invoice: Invoice | None, settings: Settings, today: date | None = None) -> tuple[bool, bool]:
    if invoice is None or invoice.due_date is None:
        return False, False
    day = today or date.today()
    overdue = invoice.due_date < day
    delta = (invoice.due_date - day).days
    near = (not overdue) and delta <= settings.NEAR_DUE_DAYS
    return overdue, near


def looks_like_vat_gross(
    *,
    invoice: Invoice,
    extracted_amount: float | None,
    settings: Settings,
) -> bool:
    if extracted_amount is None:
        return False
    extracted = Decimal(str(extracted_amount))
    net = invoice.amount
    gross = net * (Decimal("1") + Decimal(str(settings.VAT_RATE)))
    close_gross = _amounts_close(extracted, gross, settings)
    close_net = _amounts_close(extracted, net, settings)
    return close_gross and not close_net


_AMBIGUOUS = {
    InvoiceMatchResult.NOT_FOUND,
    InvoiceMatchResult.MULTIPLE,
    InvoiceMatchResult.TOO_MANY,
}


def should_retry_match(outcome: MatchOutcome, settings: Settings, retry_n: int) -> bool:
    if not settings.RESOLUTION_RETRY_ENABLED:
        return False
    if retry_n >= settings.RESOLUTION_RETRY_MAX:
        return False
    if outcome.result is InvoiceMatchResult.MATCH and outcome.method == "exact":
        return False
    if (
        outcome.result is InvoiceMatchResult.MATCH
        and outcome.confidence >= settings.RESOLUTION_RETRY_MIN_CONFIDENCE
    ):
        return False
    return (
        outcome.result in _AMBIGUOUS
        or outcome.confidence < settings.RESOLUTION_RETRY_MIN_CONFIDENCE
    )


def widened_match_settings(settings: Settings) -> Settings:
    factor = settings.RESOLUTION_RETRY_TOLERANCE_MULTIPLIER
    return settings.model_copy(
        update={
            "MATCH_VALUE_TOLERANCE_ABS": settings.MATCH_VALUE_TOLERANCE_ABS * factor,
            "MATCH_VALUE_TOLERANCE_PCT": settings.MATCH_VALUE_TOLERANCE_PCT * factor,
            "MATCH_FUZZY_CUTOFF": settings.RESOLUTION_RETRY_FUZZY_FLOOR,
        }
    )
