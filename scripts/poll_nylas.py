"""Poll the Nylas inbox and POST new mail to the local mock webhook.

No tunnel and no webhook secret. The query uses received_after set to the
moment the script starts, so a restart does not replay the mailbox. Message
ids already forwarded in this process are skipped as well. Ingest still
drops a duplicate message_id if one is posted twice.

Requires NYLAS_API_KEY and NYLAS_GRANT_ID in .env. NYLAS_API_URI must be the
Nylas host (https://api.us.nylas.com), not a tunnel URL.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.api.nylas import html_to_text  # noqa: E402
from settings import settings  # noqa: E402

API_URL = "http://127.0.0.1:8000"
INTERVAL_S = 30
PAGE_LIMIT = 10


def _get_json(url: str, api_key: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode())


def fetch_recent(
    api_uri: str,
    grant_id: str,
    api_key: str,
    received_after: int,
) -> list[dict]:
    query = urllib.parse.urlencode(
        {"limit": PAGE_LIMIT, "in": "INBOX", "received_after": received_after}
    )
    url = f"{api_uri.rstrip('/')}/v3/grants/{grant_id}/messages?{query}"
    payload = _get_json(url, api_key)
    data = payload.get("data")
    return data if isinstance(data, list) else []


def to_mock_payload(message: dict) -> dict | None:
    message_id = message.get("id")
    if not isinstance(message_id, str) or not message_id.strip():
        return None
    from_list = message.get("from")
    email = None
    if isinstance(from_list, list) and from_list and isinstance(from_list[0], dict):
        email = from_list[0].get("email")
    if not isinstance(email, str) or not email.strip():
        return None
    body = message.get("body") if isinstance(message.get("body"), str) else ""
    text = html_to_text(body) if body else ""
    if not text:
        snippet = message.get("snippet") if isinstance(message.get("snippet"), str) else ""
        text = " ".join(snippet.split())
    subject = message.get("subject") if isinstance(message.get("subject"), str) else ""
    thread_id = message.get("thread_id")
    if not isinstance(thread_id, str) or not thread_id.strip():
        thread_id = message_id.strip()
    payload = {
        "thread_id": thread_id.strip(),
        "message_id": message_id.strip(),
        "provider_message_id": message_id.strip(),
        "from": email.strip(),
        "subject": subject,
        "body": text,
    }
    raw_date = message.get("date")
    if isinstance(raw_date, (int, float)):
        payload["received_at"] = datetime.fromtimestamp(raw_date, tz=UTC).isoformat()
    return payload


def forward(payload: dict) -> int:
    request = urllib.request.Request(
        f"{API_URL}/webhook/mock",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.getcode()


def main() -> int:
    api_key = settings.NYLAS_API_KEY
    grant_id = settings.NYLAS_GRANT_ID
    api_uri = settings.NYLAS_API_URI
    if not api_key or not grant_id:
        print("NYLAS_API_KEY and NYLAS_GRANT_ID must be set in .env")
        return 1
    print(f"polling {api_uri} every {INTERVAL_S}s -> {API_URL}/webhook/mock")
    received_after = int(time.time())
    print(
        f"ignoring mail received at or before {received_after}; "
        "send a new email to create a ticket"
    )
    seen: set[str] = set()
    while True:
        try:
            messages = fetch_recent(api_uri, grant_id, api_key, received_after)
            newest = received_after
            for message in reversed(messages):
                raw_date = message.get("date")
                if isinstance(raw_date, (int, float)):
                    newest = max(newest, int(raw_date))
                message_id = message.get("id")
                if not isinstance(message_id, str) or message_id in seen:
                    continue
                seen.add(message_id)
                payload = to_mock_payload(message)
                if payload is None:
                    print(f"skip {message_id}: missing from")
                    continue
                status = forward(payload)
                subject = payload["subject"][:50] or "(no subject)"
                print(f"-> {payload['from']} | {subject} [{status}]")
            received_after = newest
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            print(f"erro HTTP {exc.code}: {detail}")
        except Exception as exc:
            print(f"erro: {exc}")
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    raise SystemExit(main())
