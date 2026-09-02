"""SAP invoice lookup port."""

from abc import ABC, abstractmethod

from app.domain.models import Invoice


class SAPPort(ABC):
    @abstractmethod
    def get_approval_invoices(self) -> list[Invoice]:
        pass

    @abstractmethod
    def get_posted_invoices(self) -> list[Invoice]:
        pass

    @abstractmethod
    def get_clearing_for_invoice(self, invoice_ref: str) -> Invoice | None:
        pass

    @abstractmethod
    def get_payment_for_invoice(self, invoice_ref: str) -> Invoice | None:
        pass
