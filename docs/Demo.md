# Demo cases — where each one stops

PowerShell. Do **not** use `curl.exe -d` — it strips JSON quotes. Use `Invoke-RestMethod`.

Postgres **5434**, Redis **6380**, API **8000**, UI **5173**.

Without `LLM_PRIMARY_API_KEY`, the live worker uses the mock LLM and always extracts `INV-2026-0001`. Only **from** / `message_id` / `thread_id` change the path. With a key, subject and body drive triage, intent, and the draft; restart the Celery worker after editing `.env`. The other invoice stories remain **eval** cases. Ticket reads and approve/escalate need the session from the login step below.

---

## Start

**Once per machine** (repo root):

```powershell
docker compose up -d
copy .env.dev .env
alembic upgrade head
python scripts/seed_operator.py --id op_joao --email joao@company.com --name "João"
```

If compose uses `lab:lab_dev`, set that in `.env` (`DATABASE_URL`). The seed script prompts for the password.

Frontend first time:

```powershell
cd frontend
copy .env.example .env
npm install
```

**Every session — 4 terminals**

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

Open `http://localhost:5173` and sign in with the operator seeded above. Keep both the UI and API on `localhost` so the session cookie is sent.

**4 — checks / ingest**

```powershell
Invoke-RestMethod -Uri http://localhost:8000/health
```

Expect `status: ok`. If Redis is up, ingest returns `task_id`; the ticket appears after Celery. If Redis is down, the same POST runs the graph in-process and returns `ticket_id`.

Log in once in this terminal. Ticket and HITL calls need the session in `$s`; the webhook does not:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/auth/login -ContentType "application/json" -Body '{"email":"joao@company.com","password":"<your password>"}' -SessionVariable s
```

Use `localhost`, not `127.0.0.1`, on every call — the cookie is tied to the host name.

After each ingest, wait a second, then UI → ticket → **Audit** (last row = node that decided), or `Show-Trail` below.

---

## Helper — trail of the last matching `message_id`

```powershell
function Show-Trail($messageId) {
  Start-Sleep -Seconds 1
  $tickets = Invoke-RestMethod -Uri http://localhost:8000/tickets -WebSession $s
  $t = $tickets | Where-Object { $_.message_id -eq $messageId } | Select-Object -Last 1
  if (-not $t) { Write-Host "no ticket yet for $messageId"; return }
  $d = Invoke-RestMethod -Uri "http://localhost:8000/tickets/$($t.id)" -WebSession $s
  Write-Host "id:" $d.id
  Write-Host "status:" $d.status
  Write-Host "audit (node -> action):"
  $d.audit | ForEach-Object { Write-Host ("  {0} -> {1}" -f $_.node, $_.action) }
}
```

---

## A. Live webhook (worker)

Change `message_id` if you already used it.

### 1. Happy path — runs to `hitl`

Stops at: **hitl** (not an early exit). Status `awaiting_human`. Has draft. Audit ends `… → resolve → draft → hitl`.

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/webhook/mock -ContentType "application/json" -Body '{"thread_id":"demo-happy","message_id":"msg-happy-1","from":"billing@acme-supplies.com","subject":"Was INV-2026-0001 paid?","body":"Please confirm payment status for INV-2026-0001 amount 1250."}'
Show-Trail "msg-happy-1"
```

Approve (only this case has a draft):

```powershell
# paste the id from Show-Trail
Invoke-RestMethod -Method POST -Uri http://localhost:8000/tickets/<ticket-uuid>/approve -ContentType "application/json" -Body '{}' -WebSession $s
```

Escalate instead of approve:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/tickets/<ticket-uuid>/escalate -WebSession $s
```

The review is recorded under the logged-in operator.

### 2. Quarantine — stops at `security`

`from` domain not in the whitelist. Audit: `ingest → security` (`quarantine`). Status `quarantined`. No draft.

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/webhook/mock -ContentType "application/json" -Body '{"thread_id":"demo-q","message_id":"msg-q-1","from":"phish@evil.example","subject":"Invoice","body":"Pay now"}'
Show-Trail "msg-q-1"
```

### 3. Delegate — stops at `routing`

Goes through ingest → security → thread → triage → intent → sender, then **routing** (`delegate`). Status `delegated`. No resolution/draft.

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/webhook/mock -ContentType "application/json" -Body '{"thread_id":"demo-del","message_id":"msg-del-1","from":"other@vendor.com","subject":"INV-2026-0001","body":"Please pay INV-2026-0001 1250 EUR."}'
Show-Trail "msg-del-1"
```

### 4. Duplicate — stops at `ingest`

Same `message_id` as an email already ingested. Status stays the **old** ticket. Audit on that id gets another `ingest` with reason duplicate (`should_stop`).

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/webhook/mock -ContentType "application/json" -Body '{"thread_id":"demo-happy","message_id":"msg-happy-1","from":"billing@acme-supplies.com","subject":"again","body":"again"}'
Show-Trail "msg-happy-1"
```

### 5. Missing ids — stops at `ingest`, **no ticket**

No row to open. The worker returns `{ ticket_id: null, status }` and does not log `missing_ids`. There is no audit row, because ingest had no ticket id.

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/webhook/mock -ContentType "application/json" -Body '{"thread_id":"","message_id":"","from":"billing@acme-supplies.com","subject":"x","body":"x"}'
```

### 6. Thread continuation — skips triage, jumps to `resolution`

Needs an **open / awaiting_human** ticket on the same `thread_id` (run happy path first with `demo-happy`). New `message_id`. The **old** ticket gets the extra body and continues; the new one is `discarded`. Open the **old** ticket in the UI.

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/webhook/mock -ContentType "application/json" -Body '{"thread_id":"demo-happy","message_id":"msg-happy-2","from":"billing@acme-supplies.com","subject":"follow-up","body":"Any update?"}'
```

---

## B. Eval only (FixtureGuidedLLM — reads the fixture `expected` block)

Worker will **not** do these: mock always uses `INV-2026-0001` / `is_ap: true`.

One fixture:

```powershell
python -c "import json,asyncio; from pathlib import Path; from scripts.eval_harness import run_fixture; r=asyncio.run(run_fixture(Path('fixtures/emails/019_paid_no_clearing.json'))); print('status', r['actual']['ticket_status']); print('match', r['actual']['invoice_resolution']); print('draft', r['actual']['draft_target']); print('hitl', r['actual']['human_action_needed'])"
```

Change the filename:

| File | Story | Status / match | Draft? | Stops conceptually at |
|---|---|---|---|---|
| `004_unknown_domain_quarantine.json` | unknown domain | `quarantined` | no | **security** |
| `005_not_ap_discard.json` | not AP | `discarded` | no | **triage** |
| `006_delegate_other_operator.json` | other operator | `delegated` | no | **routing** |
| `001_invoice_not_found.json` | no SAP hit | `awaiting_human` / `not_found` | invoicing mailbox | hitl (no early stop) |
| `003_posted_paid_clearing.json` | paid + clearing | match | sender + proof | hitl |
| `019_paid_no_clearing.json` | paid, no clearing | match | **none** | hitl, approve would 409 |
| `007_vat_discrepancy.json` | VAT gross vs net | `vat_discrepancy` | none | hitl |
| `008_multiple_sources.json` | same ref in both SAP files | `multiple` | none | hitl |
| `011_unknown_intent.json` | unknown intent | skip sender/routing | (resolution anyway) | skip_identity → resolution |

All 30 (`001`–`030`). The checked-in baseline is 29/30: fixture 022 expects a content-hash duplicate and the harness opens a fresh store per file.

```powershell
python scripts/run_eval.py
```

---

## Cheat sheet — last audit action = why it stopped

| Last `node` → `action` | Meaning |
|---|---|
| `ingest` → `ingest` (duplicate) | never left ingest. `missing_ids` leaves no ticket and no audit row |
| `security` → `quarantine` | whitelist |
| `triage` → `discard` | not AP (eval only live-mock) |
| `routing` → `delegate` | not `op_joao` |
| `hitl` → `hitl` | parked for a human |
| `hitl` then approve → `send` | only after HTTP approve |
