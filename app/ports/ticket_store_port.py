"""Ticket persistence port."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models import Ticket


class TicketStorePort(ABC):
    @abstractmethod
    def get_by_id(self, ticket_id: UUID) -> Ticket | None:
        pass

    @abstractmethod
    def get_by_message_id(self, message_id: str) -> Ticket | None:
        pass

    @abstractmethod
    def save_ticket(self, ticket: Ticket) -> Ticket:
        pass
