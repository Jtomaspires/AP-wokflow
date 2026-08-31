"""Postgres TicketStorePort adapter."""

from uuid import UUID

from sqlmodel import Session, select

from app.adapters.db_models import TicketTable
from app.domain.enums import TicketStatus
from app.domain.models import Ticket
from app.ports.ticket_store_port import TicketStorePort


def _ticket_to_table(ticket: Ticket) -> TicketTable:
    return TicketTable(
        id=ticket.id,
        thread_id=ticket.thread_id,
        message_id=ticket.message_id,
        sender_email=ticket.sender_email,
        subject=ticket.subject,
        body=ticket.body,
        received_at=ticket.received_at,
        status=ticket.status.value,
        is_ap=ticket.is_ap,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _ticket_from_table(row: TicketTable) -> Ticket:
    return Ticket(
        id=row.id,
        thread_id=row.thread_id,
        message_id=row.message_id,
        sender_email=row.sender_email,
        subject=row.subject,
        body=row.body,
        received_at=row.received_at,
        status=TicketStatus(row.status),
        is_ap=row.is_ap,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class TicketRepo(TicketStorePort):
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, ticket_id: UUID) -> Ticket | None:
        row = self.session.get(TicketTable, ticket_id)
        return _ticket_from_table(row) if row else None

    def get_by_message_id(self, message_id: str) -> Ticket | None:
        row = self.session.exec(
            select(TicketTable).where(TicketTable.message_id == message_id)
        ).first()
        return _ticket_from_table(row) if row else None

    def save_ticket(self, ticket: Ticket) -> Ticket:
        self.session.merge(_ticket_to_table(ticket))
        self.session.commit()
        return ticket
