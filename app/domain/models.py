"""Persisted domain models for the mini-lab (tickets only)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.enums import TicketStatus


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Ticket(BaseModel):
    """Email ticket persisted after ingestion."""

    thread_id: str
    message_id: str
    sender_email: str
    subject: str
    body: str
    received_at: datetime
    id: UUID = Field(default_factory=uuid4)
    status: TicketStatus = TicketStatus.OPEN
    is_ap: bool | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


    