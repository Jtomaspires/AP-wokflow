"""One Nylas v3 messages/send call. Stdlib only. The caller owns the ticket."""

import json
import urllib.error
import urllib.request


def send_reply(
    *,
    to_email: str,
    subject: str,
    body: str,
    reply_to_message_id: str | None,
    api_key: str,
    grant_id: str,
    api_uri: str,
) -> None:
    """POST the draft. Raises urllib.error.HTTPError (or URLError) on failure."""
    url = f"{api_uri.rstrip('/')}/v3/grants/{grant_id}/messages/send"
    payload = {
        "subject": subject if subject.startswith("Re:") else f"Re: {subject}",
        "body": body,
        "to": [{"email": to_email}],
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        status = getattr(response, "status", None) or response.getcode()
        if status >= 400:
            raise urllib.error.HTTPError(url, status, "Nylas send failed", hdrs=None, fp=None)
