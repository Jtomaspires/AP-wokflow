"""In-memory audit log for unit tests."""

from uuid import UUID

from app.domain.models import AuditEntry
from app.ports.audit_port import AuditPort


class InMemoryAuditStore(AuditPort):
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append(self, entry: AuditEntry) -> AuditEntry:
        self._entries.append(entry)
        return entry

    def get_by_ticket_id(self, ticket_id: UUID) -> list[AuditEntry]:
        return [e for e in self._entries if e.ticket_id == ticket_id]
