"""In-memory drafts for unit tests."""

from uuid import UUID

from app.domain.models import ResponseDraft
from app.ports.draft_port import DraftPort


class InMemoryDraftStore(DraftPort):
    def __init__(self) -> None:
        self._by_id: dict[UUID, ResponseDraft] = {}

    def save(self, draft: ResponseDraft) -> ResponseDraft:
        self._by_id[draft.id] = draft
        return draft

    def get_by_ticket_id(self, ticket_id: UUID) -> list[ResponseDraft]:
        return [d for d in self._by_id.values() if d.ticket_id == ticket_id]
