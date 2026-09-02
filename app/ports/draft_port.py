"""Outbound draft persistence port."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models import ResponseDraft


class DraftPort(ABC):
    @abstractmethod
    def save(self, draft: ResponseDraft) -> ResponseDraft:
        pass

    @abstractmethod
    def get_by_ticket_id(self, ticket_id: UUID) -> list[ResponseDraft]:
        pass
