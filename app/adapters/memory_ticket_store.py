"""In-memory ticket store for tests and local runs."""

from collections import Counter
from uuid import UUID

from app.domain.enums import TicketStatus
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

    def list_by_thread_id(self, thread_id: str) -> list[Ticket]:
        return [t for t in self._by_id.values() if t.thread_id == thread_id]

    def list_tickets(
        self,
        *,
        status: TicketStatus | None = None,
        limit: int = 100,
    ) -> list[Ticket]:
        rows = list(self._by_id.values())
        if status is not None:
            rows = [t for t in rows if t.status is status]
        return rows[:limit]

    def save_ticket(self, ticket: Ticket) -> Ticket:
        self._by_id[ticket.id] = ticket
        return ticket

    def count_by_status(self) -> dict[str, int]:
        return dict(Counter(t.status.value for t in self._by_id.values()))
