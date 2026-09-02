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
    assert ticket.status is TicketStatus.QUARANTINED
