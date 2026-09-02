"""Load senders and routing rules from fixtures/senders."""

import json
from pathlib import Path

from app.domain.models import RoutingRule, Sender
from app.ports.sender_directory_port import SenderDirectoryPort

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "senders"


def _load_list(path: Path, model):
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [model.model_validate(row) for row in raw]


class MockSenderDirectory(SenderDirectoryPort):
    def __init__(
        self,
        fixtures_dir: Path | None = None,
        senders: list[Sender] | None = None,
        rules: list[RoutingRule] | None = None,
    ) -> None:
        root = fixtures_dir or _FIXTURES
        self._senders: list[Sender] = (
            list(senders) if senders is not None else _load_list(root / "senders.json", Sender)
        )
        self._rules: list[RoutingRule] = (
            list(rules)
            if rules is not None
            else _load_list(root / "routing_rules.json", RoutingRule)
        )

    def get_by_email(self, email: str) -> Sender | None:
        needle = email.strip().lower()
        for sender in self._senders:
            if sender.email.lower() == needle:
                return sender
        return None

    def get_by_domain(self, domain: str) -> list[Sender]:
        needle = domain.strip().lower()
        found = []
        for sender in self._senders:
            if "@" in sender.email and sender.email.rsplit("@", 1)[-1].lower() == needle:
                found.append(sender)
        return found

    def get_routing_rule(
        self,
        *,
        email: str | None = None,
        domain: str | None = None,
    ) -> RoutingRule | None:
        if email:
            needle = email.strip().lower()
            for rule in self._rules:
                if rule.email and rule.email.lower() == needle:
                    return rule
        if domain:
            needle = domain.strip().lower()
            for rule in self._rules:
                if rule.domain and rule.domain.lower() == needle:
                    return rule
        return None
