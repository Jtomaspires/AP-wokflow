"""In-memory ticket store for tests and local runs."""

from uuid import UUID

from app.domain.models import Ticket
from app.ports.ticket_store_port import TicketStorePort


class InMemoryTicketStore(TicketStorePort):
    def __init__(self) -> None:
        self._by_id: dict[UUID, Ticket] = {}

    def get_by_id(self, ticket_id: UUID) -> Ticket | None:
        return self._by_id.get(ticket_id)

    def get_by_message_id(self, message_id: str) -> Ticket | None:
        for ticket in self._by_id.values():
            if ticket.message_id == message_id:
                return ticket
        return None

    def save_ticket(self, ticket: Ticket) -> Ticket:
        self._by_id[ticket.id] = ticket
        return ticket
