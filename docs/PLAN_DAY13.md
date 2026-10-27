# Day 13 — Nylas receive and reply (~3h)

> A real Nylas `message.created` notification becomes the same dict `POST /webhook/mock` already passes to `_enqueue`. Approve sends that ticket's draft through the Nylas grant, to the address the workflow already chose. Demo only. No Nylas SDK. No new graph node.
>
> Oct 12, 2026.
>
> Previous: [PLAN_DAY12.md](PLAN_DAY12.md). Charter: [README.md](README.md).

**Status:** receive and send implemented. The paragraphs below are the brief from before the work. Approve now calls Nylas when the flag, key, and grant are set. A send error leaves the ticket `awaiting_human`.

`POST /webhook/mock` in [`app/api/main.py`](../app/api/main.py) is public and calls `_enqueue(payload)`. [`MockEmailAdapter.parse_webhook`](../app/adapters/mock_email.py) reads `thread_id`, `message_id`, `from` or `from_email`, `subject`, and `body`. Ingest already stops a second ticket when the `message_id` matches, and when the sender, subject, and first 300 characters of the body match. Inbound mail still enters only through `_enqueue`. The reply is the existing approve path, which today records a send and does not call Nylas.

Quarantine and SPF/DKIM stay on `/webhook/mock`. Gmail signs mail, and this route does not set `spf_pass` or `dkim_pass`.

The other Nylas app already proved the connection. Reuse its app and its mailbox grant. Do not reuse its send behaviour.

| Other app | This lab |
|---|---|
| `GET /events/?challenge=` returns the challenge as text | `GET /webhook/nylas?challenge=` does the same |
| `POST /events/` stores the raw JSON and returns 202. The live route does not check `X-Nylas-Signature` | `POST /webhook/nylas` checks the HMAC, then normalises and calls `_enqueue` |
| Celery runs the workflow and `SendMessageNode` sends immediately | Celery only classifies. Approve is the only send |
| Recipient is always `object.from[0].email` | Recipient is `draft.to_email` |
| SDK `drafts.create` then `drafts.send` in the worker | Stdlib `POST /v3/grants/{grant}/messages/send` in the API process. That is the same call as the other app's test `messages.send`, not the draft pair |
| Subject is the original subject. Body is a fixed string | Subject is `Re: …`. Body is the Draft tab |
| `grant_id` is `object.grant_id` from the event | One mailbox, so `NYLAS_GRANT_ID` is that same grant. `reply_to_message_id` is `object.id` |
| No send flag. A Nylas error fails the Celery task | `NYLAS_SEND_ENABLED=false` keeps today's mock. A Nylas error leaves the ticket `awaiting_human` |

Do not port `config_auth.py`, `config_webhook.py`, the `EMAIL` from-filter, or an events table. The OAuth that produced the grant stays in the other app.

Demo cases that must work through Nylas:

1. A real email arrives and shows up on the dashboard.
2. That same email sent again does not create a second ticket.
3. Approve sends one reply to `draft.to_email`, which is the address `pick_target` already chose. Escalate still sends nothing.

---

## Files

### [`settings.py`](../settings.py)

Next to `NYLAS_SEND_ENABLED`:

```python
NYLAS_API_KEY: str | None = None
NYLAS_API_URI: str = "https://api.us.nylas.com"
NYLAS_GRANT_ID: str | None = None
NYLAS_WEBHOOK_SECRET: str | None = None
```

`NYLAS_SEND_ENABLED` stays default `False`. Send only when that flag is true and both the API key and the grant id are set.

Add the three optional strings to the existing empty-or-placeholder validator so `""` and `<...>` stay `None`. Secrets live only in gitignored `.env`. Do not put them in `.env.dev`. `.env.dev` keeps `NYLAS_SEND_ENABLED=false`.

### [`app/api/nylas.py`](../app/api/nylas.py) (new)

Stdlib only: `hmac`, `hashlib`, `html.parser`, `json`. No Nylas package.

**GET `/webhook/nylas`**

Nylas calls this when the webhook is created, with `?challenge=...`. Return that exact string as `text/plain` and status 200. Without this, the dashboard cannot save the webhook. No signature on this request. No enqueue.

**POST `/webhook/nylas`**

Public. No operator session.

1. Read the raw body bytes. The signature is over those bytes, not over JSON that FastAPI re-serialised.
2. If `NYLAS_WEBHOOK_SECRET` is missing, return 503. Do not accept unsigned traffic.
3. Header `X-Nylas-Signature` is the hex HMAC-SHA256 of the raw body, keyed with the secret. Compare with `hmac.compare_digest`. Missing or wrong signature: 401, and do not enqueue.
4. Parse JSON. Anything that is not a `message.created` notification: 200 and do not enqueue, so Nylas does not retry it.
5. From `data.object` build the dict `_enqueue` already accepts:

```python
{
    "thread_id": object["thread_id"],
    "message_id": object["id"],
    "from": object["from"][0]["email"],
    "subject": object.get("subject") or "",
    "body": plaintext,
}
```

`object.from` is a list of `{email, name}`. Use the first email. `object.body` is HTML. Turn it into plaintext with `html.parser` (drop tags, keep the text, collapse whitespace). If that text is empty, use `snippet`. Do not pass `spf_pass` or `dkim_pass`.

6. Call `_enqueue` and return its `task_id` with status 200.

A payload that is `message.created` but has no `from` email or no `id`: 400, no enqueue.

### [`app/api/main.py`](../app/api/main.py)

Include the router. Do not change `_enqueue`, `/webhook/mock`, or `/ingest`.

### [`tests/test_nylas_webhook.py`](../tests/test_nylas_webhook.py) (new)

Same style as `test_webhook_mock_queues_like_ingest`: patch `process_email.delay`, no network.

- [x] GET with `challenge=abc` returns `abc` as plain text.
- [x] POST with a valid signature and a `message.created` fixture calls `delay` once with `from`, `subject`, `body` plaintext, `message_id`, and `thread_id`. No `spf_pass` key.
- [x] POST with a bad signature returns 401 and does not call `delay`.
- [x] POST of another `type` returns 200 and does not call `delay`.
- [x] POST with the secret unset returns 503.

Do not duplicate the ingest duplicate tests. Those already cover the second demo case once the normalised dict is stable.

### [`app/adapters/nylas_send.py`](../app/adapters/nylas_send.py) (new)

Stdlib `urllib.request` only. No Nylas package.

```text
POST {NYLAS_API_URI}/v3/grants/{NYLAS_GRANT_ID}/messages/send
Authorization: Bearer {NYLAS_API_KEY}
```

JSON body:

```json
{
  "subject": "Re: <ticket.subject>",
  "body": "<final_text or generated_text>",
  "to": [{"email": "<draft.to_email>"}],
  "reply_to_message_id": "<ticket.message_id>"
}
```

`draft.to_email` is already set by [`_to_email`](../app/graph/nodes/draft.py): the supplier, `INVOICING_EMAIL`, `PAYMENTS_EMAIL`, or the invoice's `approval_owner_email`. Do not pick the recipient again in send. Use `draft.final_text` when the operator edited it, otherwise `draft.generated_text`. Leave the subject as-is when it already starts with `Re:`.

`reply_to_message_id` is the Nylas message id stored on the ticket by the webhook (`object.id`). The grant's mailbox is the From address. Do not send a different From. Do not call `drafts.create` or `drafts.send`.

A ticket that entered through `/webhook/mock` has a lab `message_id`. Nylas will reject that as `reply_to_message_id`. The live reply demo is a ticket that entered through `/webhook/nylas`, approved while the flag is on. `object.grant_id` on the notification must be the same value as `NYLAS_GRANT_ID`. One mailbox, so do not store a second grant on the ticket.

### [`app/graph/nodes/send.py`](../app/graph/nodes/send.py)

Today the node marks the ticket resolved and writes `metadata.nylas` without calling Nylas. Change only the send call:

- Flag off: keep the current mock. Audit `mock: true`. No HTTP.
- Flag on and key or grant missing: do not resolve the ticket. Audit `error: "nylas_not_configured"`. Return `stop_reason: "send_failed"`.
- Flag on and configured: POST the message before setting `RESOLVED`. On HTTP success, then resolve and audit `mock: false`, `nylas: true`, and `to: draft.to_email`. On HTTP failure, leave the ticket `awaiting_human`, audit the status code, and return `stop_reason: "send_failed"` so Approve can be tried again.

Escalate does not call this node. Do not add send to the inbound graph.

Approve runs in the API process, not in the Celery worker. The API process is the one that must see `NYLAS_API_KEY`.

### Tests for send

In [`tests/test_hitl.py`](../tests/test_hitl.py), patch `urllib.request.urlopen`. No network.

- [x] Flag off: approve resolves the ticket and does not open a URL.
- [x] Flag on with key and grant: the JSON `to[0].email` equals `draft.to_email`, the body is `final_text` when set and `generated_text` otherwise, and the path contains `/v3/grants/{grant}/messages/send`.
- [x] Flag on and the HTTP call fails: the ticket stays `awaiting_human`.

### Docs

Add a short "Nylas" section to [`Start.md`](../Start.md): the panel steps, the ngrok command, the whitelist note, and which address Approve will mail. Do not rewrite the mock demo.

---

## Nylas app and `.env`

Reuse the Nylas app that already has a Gmail grant. Do not run a second OAuth server in this repo.

| Other app's `.env` | This repo's `.env` | Used for |
|---|---|---|
| `NYLAS_API_KEY` | `NYLAS_API_KEY` | Bearer token on send |
| `NYLAS_API_URI` | `NYLAS_API_URI` | `https://api.us.nylas.com` unless the app is EU |
| `NYLAS_GRANT_ID` | `NYLAS_GRANT_ID` | Mailbox that receives the webhook and sends the reply |
| `WEBHOOK_SECRET` | `NYLAS_WEBHOOK_SECRET` | HMAC for **this** webhook URL. A new destination gets a new secret |
| `NYLAS_CLIENT_ID` | — | Only the other app's OAuth needs it |
| `SERVER_URL` | ngrok URL | Theirs ends in `/events`. This one ends in `/webhook/nylas` |
| `EMAIL` | — | Their dev filter. Here the gate is `SENDER_DOMAIN_WHITELIST` |
| — | `NYLAS_SEND_ENABLED` | Default `false`. `true` only on the demo machine |

1. In the Nylas v3 dashboard, create a webhook on that same app. Leave the other app's `/events` webhook as it is.
2. URL: the ngrok HTTPS URL plus `/webhook/nylas`.
3. Trigger: `message.created` only. Same trigger as `WebhookTriggers.MESSAGE_CREATED`.
4. Copy the new webhook secret into `.env` as `NYLAS_WEBHOOK_SECRET`. Do not reuse the other app's `WEBHOOK_SECRET` unless this is the same webhook destination.
5. Copy `NYLAS_API_KEY`, `NYLAS_API_URI`, and `NYLAS_GRANT_ID` from the other app. The grant is the one `config_auth.py` already stored after the Gmail consent screen.
6. Set `NYLAS_SEND_ENABLED=true` only on the machine where Approve should deliver mail. Leave it false in `.env.dev` and in tests.
7. Restart the API so it reloads `.env`. Restart the Celery worker too. The worker classifies the inbound mail. The API sends the reply on Approve.
8. The From domain of the person who writes **to** the grant must be in `SENDER_DOMAIN_WHITELIST`. Otherwise security quarantines the ticket before a draft exists. SPF/DKIM stays off for this demo (`SPF_DKIM_ENABLED` remains false). There is no `from == EMAIL` gate.

Who receives the reply is already on the draft, not a new setting:

| Workflow target | `draft.to_email` |
|---|---|
| Supplier | The inbound sender |
| Invoicing | `INVOICING_EMAIL` |
| Payments | `PAYMENTS_EMAIL` |
| Approval owner | The invoice's `approval_owner_email` |

`INV-2026-0001` is overdue on 12 Oct 2026, so a mail about that invoice drafts to `ap-owner@company.com`, not back to the supplier. A mail that matches no invoice drafts to `invoicing@company.com`. Approve sends whatever the Draft tab shows. Cases with no draft still cannot be approved.

---

## ngrok

The API is on port 8000. The UI stays on `http://localhost:5173`.

```powershell
ngrok http 8000
```

Use the `https://....ngrok-free.app` URL in the Nylas webhook. Leave that terminal open during the demo. A new ngrok URL means updating the webhook in the panel.

Confirm Nylas saved the webhook. That only succeeds after GET returns the challenge.

---

## Before the demo

1. `pytest tests/test_nylas_webhook.py tests/test_api.py` — the mock webhook test must still pass.
2. API, worker, Postgres, Redis, and the UI are up. Open `http://localhost:5173`.
3. Send one real email to the connected mailbox. Refresh the dashboard. One new ticket, with that subject and sender.
4. Send the same email again (same sender, subject, and body, not a reply that adds quoted text). Refresh. Still one ticket. Ingest stops it as a duplicate. The content hash uses the plaintext body, so the strip function has to be stable.
5. Do not use this path to show quarantine or SPF/DKIM. Use `/webhook/mock` for those.
6. Open the ticket, read the Draft tab, and Approve. The mailbox in `to` on that draft receives one message from the Nylas grant, with subject `Re: <original subject>`. Escalate does not send. With `NYLAS_SEND_ENABLED=false`, Approve still only resolves the ticket.

---

## Do not

- Install the Nylas SDK. Receive and send both use the stdlib. Do not call `drafts.create` or `drafts.send`.
- Add OAuth routes, `NYLAS_CLIENT_ID`, or a `/nylas/send-email` test. The grant already exists.
- Send to `object.from[0]` just because the other workflow does. The draft already chose the address.
- Send on escalate, send from the worker, or send when the flag is off.
- Add a graph node, a new queue, or a table for the raw notification.
- Put operator auth on `/webhook/nylas`.
- Change ingest, the content hash, or `/webhook/mock`.
- Invent SPF/DKIM results from Gmail.
- Commit `.env` or the webhook secret.
