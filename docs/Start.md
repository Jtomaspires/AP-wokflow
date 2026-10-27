# Start

PowerShell. Four terminals from the repo root. Postgres **5434**, Redis **6380**, API **8000**, UI **5173**.

Do **not** use `curl.exe -d "{...}"` here — PowerShell strips the quotes and FastAPI returns `json_invalid`. Use `Invoke-RestMethod`.

---

## Once per machine

```powershell
docker compose up -d
copy .env.dev .env
alembic upgrade head
python scripts/seed_operator.py --id op_joao --email joao@company.com --name "João"
```

If compose uses `lab:lab_dev`, set that in `.env` (`DATABASE_URL`).

The seed script prompts for the password twice. Run it again to reset it.

Frontend (first time):

```powershell
cd frontend
copy .env.example .env
npm install
```

---

## Every session (4 terminals)

**1 — API**

```powershell
uvicorn app.api.main:app --reload --port 8000
```

**2 — Worker (Windows)**

```powershell
celery -A app.worker.tasks:celery_app worker --pool=solo --loglevel=info
```

**3 — Operator UI**

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173` and sign in with the seeded operator. API is `http://localhost:8000` (`VITE_API_URL`). Do not mix `localhost` and `127.0.0.1`, or the browser will not send the session cookie.

**4 — checks / ingest** (this terminal)

```powershell
Invoke-RestMethod -Uri http://localhost:8000/health
```

Expect `status: ok`.

If Redis is up, ingest returns `task_id` (202). The ticket shows up after Celery finishes. If Redis is down, the same POST runs the graph in-process and returns `ticket_id`.

---

## Demo ingest (unique `message_id` each time)

Happy path — `awaiting_human` + draft. Without an API key the mock stays on `INV-2026-0001`:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/webhook/mock -ContentType "application/json" -Body '{"thread_id":"demo-paid","message_id":"msg-demo-paid-1","from":"billing@acme-supplies.com","subject":"Was INV-2026-0001 paid?","body":"Please confirm payment status for INV-2026-0001 amount 1250."}'
```

Quarantine — `evil.example` → `quarantined`:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/webhook/mock -ContentType "application/json" -Body '{"thread_id":"demo-quarantine","message_id":"msg-demo-quarantine-1","from":"phish@evil.example","subject":"Invoice","body":"Pay now"}'
```

Delegate — `other@vendor.com` → `delegated`:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/webhook/mock -ContentType "application/json" -Body '{"thread_id":"demo-delegate","message_id":"msg-demo-delegate-1","from":"other@vendor.com","subject":"INV-2026-0001 status","body":"Please pay INV-2026-0001 1250 EUR."}'
```

List / approve — log in first; `$s` keeps the session cookie for the next calls:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/auth/login -ContentType "application/json" -Body '{"email":"joao@company.com","password":"<your password>"}' -SessionVariable s
Invoke-RestMethod -Uri http://localhost:8000/tickets -WebSession $s
Invoke-RestMethod -Method POST -Uri http://localhost:8000/tickets/<ticket-uuid>/approve -ContentType "application/json" -Body '{}' -WebSession $s
```

The approver is the logged-in operator. Without a session, ticket and HITL routes return 401; the webhook and `/health` stay public.

Repeat ingest: change the sender, subject, or body as well as `message_id`. The same from, subject, and first 300 characters of body stop as a content duplicate even when `message_id` is new.

Without `LLM_PRIMARY_API_KEY`, the worker uses the mock and always extracts `INV-2026-0001`. With a key, restart the worker so triage and the draft follow the email. Paid-without-clearing is fixture `019` in eval.

Case-by-case commands (which node stops, live vs eval): [Demo.md](Demo.md).

---

## Nylas receive

The mock commands above stay as they are. A real mailbox does not need a tunnel. From the repo root, with the API and the worker already running:

```powershell
python scripts/poll_nylas.py
```

That process lists messages received after it starts and posts them to `/webhook/mock`. No operator session. It does not send mail.

The alternative is a Nylas `message.created` webhook on this API. Same rule: no operator session, and this route does not send mail.

```powershell
ngrok http 8000
```

Leave that terminal open. In the Nylas app that already has the Gmail grant, add a webhook and leave the other app's `/events` webhook alone.

- URL: the ngrok `https://....ngrok-free.app` host plus `/webhook/nylas`.
- Trigger: `message.created` only.
- Copy that webhook's secret into `.env` as `NYLAS_WEBHOOK_SECRET`. A new URL gets a new secret. Do not put it in `.env.dev`.

Restart the API and the worker after `.env` changes. The From domain of the person who writes to the grant must be in `SENDER_DOMAIN_WHITELIST`, or security quarantines the ticket. `SPF_DKIM_ENABLED` stays false. Nylas can save the webhook only after GET `/webhook/nylas?challenge=...` echoes the challenge.

Approve sends the Draft tab only when `NYLAS_SEND_ENABLED=true` and both `NYLAS_API_KEY` and `NYLAS_GRANT_ID` are set. The recipient is the address already on that draft. Leave the flag false until you want a real reply. Escalate does not send. Restart the API after changing the flag: Approve runs in the API process, not in the worker.

---

## Eval (no Docker)

```powershell
python scripts/run_eval.py
```

Writes `golden_dataset/baselines/v1.json`.
