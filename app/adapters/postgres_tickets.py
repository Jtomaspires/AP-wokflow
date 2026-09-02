"""Postgres TicketStorePort adapter."""

from collections import Counter
from uuid import UUID

from sqlmodel import Session, select

from app.adapters.db_models import TicketTable
from app.domain.enums import Intent, TicketStatus
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
        intent=ticket.intent.value if ticket.intent else None,
        language=ticket.language,
        assigned_operator_id=ticket.assigned_operator_id,
        confidence=ticket.confidence,
        is_thread_continuation=ticket.is_thread_continuation,
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
        intent=Intent(row.intent) if row.intent else None,
        language=row.language,
        assigned_operator_id=row.assigned_operator_id,
        confidence=row.confidence,
        is_thread_continuation=row.is_thread_continuation,
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

    def list_by_thread_id(self, thread_id: str) -> list[Ticket]:
        rows = self.session.exec(
            select(TicketTable).where(TicketTable.thread_id == thread_id)
        ).all()
        return [_ticket_from_table(row) for row in rows]

    def list_tickets(
        self,
        *,
        status: TicketStatus | None = None,
        limit: int = 100,
    ) -> list[Ticket]:
        stmt = select(TicketTable)
        if status is not None:
            stmt = stmt.where(TicketTable.status == status.value)
        stmt = stmt.limit(limit)
        return [_ticket_from_table(row) for row in self.session.exec(stmt).all()]

    def save_ticket(self, ticket: Ticket) -> Ticket:
        self.session.merge(_ticket_to_table(ticket))
        self.session.commit()
        return ticket

    def count_by_status(self) -> dict[str, int]:
        rows = self.session.exec(select(TicketTable.status)).all()
        return dict(Counter(rows))
