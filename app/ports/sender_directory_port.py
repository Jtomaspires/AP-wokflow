"""Known senders and routing rules."""

from abc import ABC, abstractmethod

from app.domain.models import RoutingRule, Sender


class SenderDirectoryPort(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> Sender | None:
        pass

    @abstractmethod
    def get_by_domain(self, domain: str) -> list[Sender]:
        pass

    @abstractmethod
    def get_routing_rule(
        self,
        *,
        email: str | None = None,
        domain: str | None = None,
    ) -> RoutingRule | None:
        pass
