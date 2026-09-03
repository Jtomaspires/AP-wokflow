"""Invoice reference matching (exact → fuzzy → amount+supplier). No retry loop."""

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


def match_invoices(
    *,
    approval: list[Invoice],
    posted: list[Invoice],
    extracted_ref: str | None,
    extracted_amount: float | None,
    supplier_hint: str | None,
    settings: Settings,
) -> MatchOutcome:
    pool = list(approval) + list(posted)
    needle = normalize_reference(extracted_ref)

    exact_app = [i for i in approval if needle and normalize_reference(i.invoice_ref) == needle]
    exact_post = [i for i in posted if needle and normalize_reference(i.invoice_ref) == needle]
    exact = exact_app + exact_post
    if len(exact_app) >= 1 and len(exact_post) >= 1:
        return MatchOutcome(InvoiceMatchResult.MULTIPLE, "exact", None, True)
    if len(exact) > 1:
        return MatchOutcome(InvoiceMatchResult.TOO_MANY, "exact", None, True)
    if len(exact) == 1:
        return MatchOutcome(InvoiceMatchResult.MATCH, "exact", exact[0], False)

    if needle:
        fuzzy_hits = [
            inv
            for inv in pool
            if _fuzzy(normalize_reference(inv.invoice_ref), needle) >= 0.85
        ]
        if len(fuzzy_hits) > 3:
            return MatchOutcome(InvoiceMatchResult.TOO_MANY, "fuzzy", None, True)
        if len(fuzzy_hits) > 1:
            return MatchOutcome(InvoiceMatchResult.MULTIPLE, "fuzzy", None, True)
        if len(fuzzy_hits) == 1:
            return MatchOutcome(InvoiceMatchResult.MATCH, "fuzzy", fuzzy_hits[0], False)

    amount = Decimal(str(extracted_amount)) if extracted_amount is not None else None
    if amount is not None and supplier_hint:
        amount_hits = [
            inv
            for inv in pool
            if _amounts_close(inv.amount, amount, settings)
            and _supplier_close(inv.supplier_name, supplier_hint)
        ]
        if len(amount_hits) > 1:
            return MatchOutcome(InvoiceMatchResult.MULTIPLE, "amount", None, True)
        if len(amount_hits) == 1:
            return MatchOutcome(InvoiceMatchResult.MATCH, "amount", amount_hits[0], False)

    return MatchOutcome(InvoiceMatchResult.NOT_FOUND, None, None, False)


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
