"""Cookie session auth: login, me, logout, protected routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from sqlmodel import Session

from app.adapters.db_models import OperatorSessionTable
from app.adapters.postgres_repos import DraftRepo, HumanReviewRepo
from app.adapters.postgres_tickets import TicketRepo
from app.api.main import app
from app.auth.passwords import hash_password
from app.auth.repo import AuthRepo
from app.auth.tokens import new_token, token_hash
from app.domain.enums import DraftTarget, TicketStatus
from app.domain.models import Operator, ResponseDraft, Ticket
from app.worker.tasks import engine
from settings import settings

PASSWORD = "correct horse battery staple"


def _seed(*, is_active: bool = True) -> Operator:
    suffix = uuid4().hex[:8]
    operator = Operator(
        id=f"op_test_{suffix}",
        email=f"Test.{suffix}@Company.com",
        display_name="Test Operator",
        is_active=is_active,
    )
    with Session(engine) as session:
        return AuthRepo(session).upsert_operator(operator, hash_password(PASSWORD))


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _login(client, operator: Operator, password: str = PASSWORD) -> httpx.Response:
    return await client.post("/auth/login", json={"email": operator.email, "password": password})


async def test_login_sets_httponly_cookie(client):
    operator = _seed()
    response = await _login(client, operator)

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{settings.SESSION_COOKIE_NAME}=")
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    assert response.json() == {
        "id": operator.id,
        "email": operator.email,
        "display_name": "Test Operator",
    }
    assert "password_hash" not in response.text


async def test_login_email_is_case_insensitive(client):
    operator = _seed()
    response = await client.post(
        "/auth/login", json={"email": f"  {operator.email.upper()} ", "password": PASSWORD}
    )
    assert response.status_code == 200


async def test_wrong_password_and_unknown_email_look_the_same(client):
    operator = _seed()
    wrong = await _login(client, operator, password="nope")
    unknown = await client.post(
        "/auth/login", json={"email": "nobody@company.com", "password": PASSWORD}
    )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "invalid credentials"}


async def test_inactive_operator_cannot_log_in(client):
    operator = _seed(is_active=False)
    response = await _login(client, operator)
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


async def test_me_requires_session(client):
    assert (await client.get("/auth/me")).status_code == 401

    operator = _seed()
    await _login(client, operator)
    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == operator.id


async def test_logout_revokes_the_session(client):
    operator = _seed()
    await _login(client, operator)
    token = client.cookies[settings.SESSION_COOKIE_NAME]

    logout = await client.post("/auth/logout")
    assert logout.status_code == 204

    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    assert (await client.get("/auth/me")).status_code == 401


async def test_expired_session_is_rejected(client):
    operator = _seed()
    token = new_token()
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(
            OperatorSessionTable(
                token_hash=token_hash(token),
                operator_id=operator.id,
                created_at=now - timedelta(hours=13),
                expires_at=now - timedelta(hours=1),
            )
        )
        session.commit()

    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    assert (await client.get("/auth/me")).status_code == 401


async def test_protected_routes_require_session(client):
    ticket_id = uuid4()
    assert (await client.get("/tickets")).status_code == 401
    assert (await client.get("/stats")).status_code == 401
    assert (await client.get(f"/tickets/{ticket_id}")).status_code == 401
    assert (await client.get(f"/tickets/{ticket_id}/draft")).status_code == 401
    assert (await client.post(f"/tickets/{ticket_id}/approve", json={})).status_code == 401
    assert (await client.post(f"/tickets/{ticket_id}/escalate")).status_code == 401


async def test_health_and_webhook_stay_public(client):
    assert (await client.get("/health")).status_code == 200
    fake = MagicMock()
    fake.id = "task-public"
    with patch("app.api.main.process_email.delay", return_value=fake):
        response = await client.post(
            "/webhook/mock",
            json={"thread_id": "t", "message_id": "m", "from": "x@y.com", "subject": "x", "body": "x"},
        )
    assert response.status_code == 202


async def test_approve_records_session_operator_not_body(client):
    operator = _seed()
    ticket = Ticket(
        thread_id=f"thread-auth-{uuid4().hex[:8]}",
        message_id=f"msg-auth-{uuid4().hex[:8]}",
        sender_email="billing@acme-supplies.com",
        subject="Invoice",
        body="Hello",
        received_at=datetime(2026, 8, 21, tzinfo=UTC),
        status=TicketStatus.AWAITING_HUMAN,
    )
    with Session(engine) as session:
        ticket = TicketRepo(session).save_ticket(ticket)
        DraftRepo(session).save(
            ResponseDraft(
                ticket_id=ticket.id,
                target=DraftTarget.SENDER,
                to_email=ticket.sender_email,
                generated_text="Draft body",
            )
        )

    await _login(client, operator)
    response = await client.post(
        f"/tickets/{ticket.id}/approve", json={"operator_id": "op_someone_else"}
    )
    assert response.status_code == 200

    with Session(engine) as session:
        reviews = HumanReviewRepo(session).get_by_ticket_id(ticket.id)
    assert [r.operator_id for r in reviews] == [operator.id]
