"""FastAPI health, ingest, tickets (Day 2)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from sqlmodel import Session

from app.adapters.postgres_tickets import TicketRepo
from app.api.main import app
from app.domain.enums import TicketStatus
from app.domain.models import Ticket
from app.worker.tasks import engine


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_get_ticket_404(client):
    response = await client.get(f"/tickets/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_ticket_from_postgres(client):
    ticket = Ticket(
        thread_id=f"thread-api-{uuid4().hex[:8]}",
        message_id=f"msg-api-{uuid4().hex[:8]}",
        sender_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Hello",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
        status=TicketStatus.OPEN,
    )
    with Session(engine) as session:
        saved = TicketRepo(session).save_ticket(ticket)

    response = await client.get(f"/tickets/{saved.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(saved.id)
    assert body["message_id"] == saved.message_id
    assert body["status"] == "open"


@pytest.mark.asyncio
async def test_ingest_queues_celery_task(client):
    payload = {
        "thread_id": "thread-1",
        "message_id": "msg-1",
        "from": "billing@acme-supplies.com",
        "subject": "Invoice",
        "body": "Hello",
    }
    fake = MagicMock()
    fake.id = "task-abc"
    with patch("app.api.main.process_email.delay", return_value=fake) as delay:
        response = await client.post("/ingest", json=payload)

    assert response.status_code == 202
    assert response.json() == {"task_id": "task-abc"}
    delay.assert_called_once_with(payload)


def test_ingest_falls_back_sync_when_redis_down():
    from app.api.main import ingest, get_ticket

    payload = {
        "thread_id": "thread-fb",
        "message_id": f"msg-fb-{uuid4().hex[:8]}",
        "from": "phish@evil.example",
        "subject": "Hi",
        "body": "x",
    }
    with patch("app.api.main.process_email.delay", side_effect=ConnectionError("redis")):
        body = ingest(payload)

    assert body["status"] == "quarantined"
    assert body["ticket_id"] is not None
    ticket = get_ticket(UUID(body["ticket_id"]))
    assert ticket["status"] == "quarantined"


@pytest.mark.asyncio
async def test_webhook_mock_queues_like_ingest(client):
    payload = {
        "thread_id": "thread-1",
        "message_id": "msg-wh",
        "from": "billing@acme-supplies.com",
        "subject": "Invoice",
        "body": "Hello",
    }
    fake = MagicMock()
    fake.id = "task-wh"
    with patch("app.api.main.process_email.delay", return_value=fake) as delay:
        response = await client.post("/webhook/mock", json=payload)
    assert response.status_code == 202
    assert response.json() == {"task_id": "task-wh"}
    delay.assert_called_once_with(payload)


@pytest.mark.asyncio
async def test_approve_and_escalate_http(client):
    from app.adapters.postgres_repos import DraftRepo
    from app.domain.enums import DraftTarget
    from app.domain.models import ResponseDraft

    waiting = Ticket(
        thread_id=f"thread-hitl-{uuid4().hex[:8]}",
        message_id=f"msg-hitl-{uuid4().hex[:8]}",
        sender_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Hello",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
        status=TicketStatus.AWAITING_HUMAN,
    )
    open_ticket = Ticket(
        thread_id=f"thread-open-{uuid4().hex[:8]}",
        message_id=f"msg-open-{uuid4().hex[:8]}",
        sender_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Hello",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
        status=TicketStatus.OPEN,
    )
    with Session(engine) as session:
        waiting = TicketRepo(session).save_ticket(waiting)
        open_ticket = TicketRepo(session).save_ticket(open_ticket)
        DraftRepo(session).save(
            ResponseDraft(
                ticket_id=waiting.id,
                target=DraftTarget.SENDER,
                to_email=waiting.sender_email,
                generated_text="Draft body",
            )
        )

    draft_res = await client.get(f"/tickets/{waiting.id}/draft")
    assert draft_res.status_code == 200
    assert draft_res.json()["generated_text"] == "Draft body"

    listed = await client.get("/tickets")
    assert listed.status_code == 200
    assert any(row["id"] == str(waiting.id) for row in listed.json())

    stats = await client.get("/stats")
    assert stats.status_code == 200
    assert isinstance(stats.json(), dict)

    bad = await client.post(
        f"/tickets/{open_ticket.id}/approve",
        json={"operator_id": "op_joao"},
    )
    assert bad.status_code == 409

    ok = await client.post(
        f"/tickets/{waiting.id}/approve",
        json={"operator_id": "op_joao", "final_text": "Edited send"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "resolved"

    detail = await client.get(f"/tickets/{waiting.id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "resolved"
    assert detail.json()["draft"]["edited_by_human"] is True

    esc_ticket = Ticket(
        thread_id=f"thread-esc-{uuid4().hex[:8]}",
        message_id=f"msg-esc-{uuid4().hex[:8]}",
        sender_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Hello",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
        status=TicketStatus.AWAITING_HUMAN,
    )
    with Session(engine) as session:
        esc_ticket = TicketRepo(session).save_ticket(esc_ticket)

    esc = await client.post(
        f"/tickets/{esc_ticket.id}/escalate",
        json={"operator_id": "op_joao"},
    )
    assert esc.status_code == 200
    assert esc.json()["status"] == "escalated"
