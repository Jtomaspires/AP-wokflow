"""In-memory HITL reviews."""

from uuid import UUID

from app.domain.models import HumanReview


class InMemoryReviewStore:
    def __init__(self) -> None:
        self._items: list[HumanReview] = []

    def save(self, review: HumanReview) -> HumanReview:
        self._items.append(review)
        return review

    def get_by_ticket_id(self, ticket_id: UUID) -> list[HumanReview]:
        return [r for r in self._items if r.ticket_id == ticket_id]
