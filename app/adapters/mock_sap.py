"""Load SAP invoice JSON from fixtures/sap_mock (do not regenerate)."""

import json
from pathlib import Path

from app.domain.models import Invoice
from app.ports.sap_port import SAPPort

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "sap_mock"


def _load_from(path: Path) -> list[Invoice]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Invoice.model_validate(row) for row in raw]


class MockSAPAdapter(SAPPort):
    def __init__(
        self,
        fixtures_dir: Path | None = None,
        *,
        approval: list[Invoice] | None = None,
        posted: list[Invoice] | None = None,
    ) -> None:
        root = fixtures_dir or _FIXTURES
        self._approval = list(approval) if approval is not None else _load_from(root / "approval.json")
        self._posted = list(posted) if posted is not None else _load_from(root / "posted.json")

    def get_approval_invoices(self) -> list[Invoice]:
        return list(self._approval)

    def get_posted_invoices(self) -> list[Invoice]:
        return list(self._posted)

    def get_clearing_for_invoice(self, invoice_ref: str) -> Invoice | None:
        for inv in self._posted:
            if inv.invoice_ref == invoice_ref and inv.clearing_document:
                return inv
        return None

    def get_payment_for_invoice(self, invoice_ref: str) -> Invoice | None:
        for inv in self._posted:
            if inv.invoice_ref == invoice_ref and inv.payment_document:
                return inv
        return None
