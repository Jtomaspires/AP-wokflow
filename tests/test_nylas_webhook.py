"""Nylas message.created webhook: challenge, HMAC, and the mock enqueue dict."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.api.main import app
from settings import Settings, settings

_SECRET = "test-webhook-secret"


def _body(payload: dict) -> bytes:
    return json.dumps(payload).encode()


def _sign(body: bytes, secret: str = _SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _message_created() -> dict:
    return {
        "specversion": "1.0",
        "type": "message.created",
        "id": "delivery-id",
        "data": {
            "object": {
                "id": "msg-nylas-1",
                "grant_id": "grant-other",
                "thread_id": "thread-nylas-1",
                "subject": "Invoice",
                "from": [{"name": "Billing", "email": "billing@acme-supplies.com"}],
                "body": "<p>Hello</p><script>alert(1)</script>",
                "snippet": "ignored when body has text",
            }
        },
    }


@pytest.fixture
def nylas_secret(monkeypatch):
    monkeypatch.setattr(settings, "NYLAS_WEBHOOK_SECRET", _SECRET)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_empty_webhook_secret_and_placeholder_are_none():
    assert Settings(NYLAS_WEBHOOK_SECRET="").NYLAS_WEBHOOK_SECRET is None
    assert Settings(NYLAS_WEBHOOK_SECRET="<secret>").NYLAS_WEBHOOK_SECRET is None
    assert Settings(NYLAS_API_KEY="").NYLAS_API_KEY is None
    assert Settings(NYLAS_GRANT_ID="<grant>").NYLAS_GRANT_ID is None
    assert Settings(NYLAS_API_URI="").NYLAS_API_URI == "https://api.us.nylas.com"


@pytest.mark.asyncio
async def test_challenge_returns_plain_text(client):
    response = await client.get("/webhook/nylas", params={"challenge": "abc"})
    assert response.status_code == 200
    assert response.text == "abc"
    assert response.headers["content-type"].startswith("text/plain")


@pytest.mark.asyncio
async def test_valid_signature_enqueues_plaintext(client, nylas_secret):
    raw = _body(_message_created())
    fake = MagicMock()
    fake.id = "task-nylas"
    with patch("app.api.main.process_email.delay", return_value=fake) as delay:
        response = await client.post(
            "/webhook/nylas",
            content=raw,
            headers={
                "X-Nylas-Signature": _sign(raw),
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200
    assert response.json() == {"task_id": "task-nylas"}
    delay.assert_called_once_with(
        {
            "thread_id": "thread-nylas-1",
            "message_id": "msg-nylas-1",
            "provider_message_id": "msg-nylas-1",
            "from": "billing@acme-supplies.com",
            "subject": "Invoice",
            "body": "Hello",
        }
    )
    assert "spf_pass" not in delay.call_args.args[0]
    assert "dkim_pass" not in delay.call_args.args[0]


@pytest.mark.asyncio
async def test_bad_signature_is_401(client, nylas_secret):
    raw = _body(_message_created())
    with patch("app.api.main.process_email.delay") as delay:
        response = await client.post(
            "/webhook/nylas",
            content=raw,
            headers={"X-Nylas-Signature": "0" * 64},
        )
    assert response.status_code == 401
    delay.assert_not_called()


@pytest.mark.asyncio
async def test_other_type_is_ignored(client, nylas_secret):
    raw = _body({"type": "message.updated", "data": {}})
    with patch("app.api.main.process_email.delay") as delay:
        response = await client.post(
            "/webhook/nylas",
            content=raw,
            headers={"X-Nylas-Signature": _sign(raw)},
        )
    assert response.status_code == 200
    delay.assert_not_called()


@pytest.mark.asyncio
async def test_secret_unset_is_503(client, monkeypatch):
    monkeypatch.setattr(settings, "NYLAS_WEBHOOK_SECRET", None)
    raw = _body(_message_created())
    with patch("app.api.main.process_email.delay") as delay:
        response = await client.post(
            "/webhook/nylas",
            content=raw,
            headers={"X-Nylas-Signature": _sign(raw)},
        )
    assert response.status_code == 503
    delay.assert_not_called()
