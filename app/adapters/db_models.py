"""SQLModel table for tickets (separate from the Pydantic Ticket)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TicketTable(SQLModel, table=True):
    __tablename__ = "tickets"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    thread_id: str = Field(index=True)
    message_id: str = Field(index=True, unique=True)
    sender_email: str = Field(index=True)
    subject: str
    body: str = Field(sa_column=Column(Text, nullable=False))
    received_at: datetime
    status: str = Field(index=True)
    is_ap: bool | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)