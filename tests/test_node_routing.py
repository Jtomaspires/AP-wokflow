"""Routing when the sender has no rule."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.adapters.memory_ticket_store import InMemoryTicketStore
from app.adapters.mock_sender_directory import MockSenderDirectory
from app.domain.enums import TicketStatus
from app.domain.models import RoutingRule, Ticket
from app.graph.nodes.routing import make_routing_node
from settings import Settings
from tests.helpers import make_test_deps


def _saved_ticket(store: InMemoryTicketStore, *, sender: str) -> Ticket:
    ticket = Ticket(
        thread_id="th-route",
        message_id=f"msg-{uuid4().hex[:8]}",
        sender_email=sender,
        subject="Invoice",
        body="Pay",
        received_at=datetime(2026, 8, 1, tzinfo=UTC),
        status=TicketStatus.OPEN,
    )
    store.save_ticket(ticket)
    return ticket


def _route(store: InMemoryTicketStore, ticket: Ticket, *, behaviour: str, rules: list[RoutingRule]):
    deps = make_test_deps(
        tickets=store,
        senders=MockSenderDirectory(senders=[], rules=rules),
        settings=Settings(
            DEFAULT_OPERATOR_ID="op_joao",
            ROUTING_NO_RULE_BEHAVIOUR=behaviour,
        ),
    )
    update = make_routing_node(deps)({"ticket_id": str(ticket.id)})
    saved = store.get_by_id(ticket.id)
    assert saved is not None
    return update, saved


def test_no_rule_default_assigns_op_joao():
    store = InMemoryTicketStore()
    ticket = _saved_ticket(store, sender="nobody@unknown.example")
    update, saved = _route(store, ticket, behaviour="default", rules=[])
    assert saved.assigned_operator_id == "op_joao"
    assert update["routing_outcome"] == "no_rule_default"
    assert update["should_stop"] is False


def test_no_rule_hitl_leaves_operator_unset():
    store = InMemoryTicketStore()
    ticket = _saved_ticket(store, sender="nobody@unknown.example")
    update, saved = _route(store, ticket, behaviour="hitl", rules=[])
    assert saved.assigned_operator_id is None
    assert update["routing_outcome"] == "no_rule_hitl"
    assert update["should_stop"] is False


@pytest.mark.parametrize("behaviour", ["default", "hitl"])
def test_existing_rule_ignores_no_rule_setting(behaviour: str):
    store = InMemoryTicketStore()
    ticket = _saved_ticket(store, sender="other@vendor.com")
    rule = RoutingRule(id="rule-x", operator_id="op_other", email="other@vendor.com")
    update, saved = _route(store, ticket, behaviour=behaviour, rules=[rule])
    assert saved.status is TicketStatus.DELEGATED
    assert saved.assigned_operator_id == "op_other"
    assert "routing_outcome" not in update
