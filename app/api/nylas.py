"""Public Nylas message.created webhook. Stdlib only. Does not send mail."""

import hashlib
import hmac
import json
from html.parser import HTMLParser
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse

from settings import settings

router = APIRouter(tags=["nylas"])

_SKIP_TAGS = frozenset({"script", "style"})


class _TextExtractor(HTMLParser):
    """Drop tags and skip script/style, keeping the visible text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in _SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self._parts).split())


def html_to_text(raw: str) -> str:
    parser = _TextExtractor()
    parser.feed(raw)
    parser.close()
    return parser.text()


def _signature_ok(body: bytes, header: str | None, secret: str) -> bool:
    if not header:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    provided = header.strip()
    if len(provided) != len(expected):
        return False
    return hmac.compare_digest(expected, provided)


def _normalise(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if not isinstance(obj, dict):
        raise HTTPException(status_code=400, detail="message.created missing object")
    message_id = obj.get("id")
    from_list = obj.get("from")
    email = None
    if isinstance(from_list, list) and from_list and isinstance(from_list[0], dict):
        email = from_list[0].get("email")
    if not isinstance(message_id, str) or not message_id.strip():
        raise HTTPException(status_code=400, detail="message.created missing id")
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(status_code=400, detail="message.created missing from")
    body = obj.get("body") if isinstance(obj.get("body"), str) else ""
    text = html_to_text(body) if body else ""
    if not text:
        snippet = obj.get("snippet") if isinstance(obj.get("snippet"), str) else ""
        text = " ".join(snippet.split())
    subject = obj.get("subject") or ""
    if not isinstance(subject, str):
        subject = ""
    normalised: dict[str, Any] = {
        "message_id": message_id.strip(),
        "provider_message_id": message_id.strip(),
        "from": email.strip(),
        "subject": subject,
        "body": text,
    }
    thread_id = obj.get("thread_id")
    if isinstance(thread_id, str) and thread_id:
        normalised["thread_id"] = thread_id
    return normalised


@router.get("/webhook/nylas")
def nylas_challenge(challenge: str | None = None) -> PlainTextResponse:
    if not challenge:
        raise HTTPException(status_code=400, detail="missing challenge")
    return PlainTextResponse(challenge, status_code=200)


@router.post("/webhook/nylas")
async def nylas_webhook(request: Request) -> JSONResponse:
    from app.api.main import _enqueue

    raw = await request.body()
    secret = settings.NYLAS_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(status_code=503, detail="nylas webhook secret is not configured")
    header = request.headers.get("x-nylas-signature")
    if not _signature_ok(raw, header, secret):
        raise HTTPException(status_code=401, detail="invalid signature")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc
    if not isinstance(payload, dict) or payload.get("type") != "message.created":
        return JSONResponse({}, status_code=200)
    result = _enqueue(_normalise(payload))
    return JSONResponse(content=jsonable_encoder(result), status_code=200)
