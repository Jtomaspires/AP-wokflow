"""Ticket persistence port."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.enums import TicketStatus
from app.domain.models import Ticket


class TicketStorePort(ABC):
    @abstractmethod
    def get_by_id(self, ticket_id: UUID) -> Ticket | None:
        pass

    @abstractmethod
    def get_by_message_id(self, message_id: str) -> Ticket | None:
        pass

    @abstractmethod
    def list_by_thread_id(self, thread_id: str) -> list[Ticket]:
        pass

    @abstractmethod
    def list_tickets(
        self,
        *,
        status: TicketStatus | None = None,
        limit: int = 100,
    ) -> list[Ticket]:
        pass

    @abstractmethod
    def save_ticket(self, ticket: Ticket) -> Ticket:
        pass

    @abstractmethod
    def count_by_status(self) -> dict[str, int]:
        pass
