# p2p-ai-langraph

**POST /ingest** or **POST /webhook/mock** → Redis → Celery → LangGraph (through HITL) → Postgres. Approve/escalate via HTTP; send is not on the inbound spine.

Triage talks to `LLMPort`, not `openai`. Security uses only `settings` + ticket store (sender-domain whitelist).

## Run (three terminals)

From this directory. Postgres **5434**, Redis **6380**.

```powershell
docker compose up -d
copy .env.dev .env
```

Fix `DATABASE_URL` in `.env` to `lab:lab_dev` if compose uses those credentials.

```powershell
alembic upgrade head
```

**1 — API**

```powershell
uvicorn app.api.main:app --reload --port 8000
```

**2 — Worker (Windows: `--pool=solo`)**

```powershell
celery -A app.worker.tasks:celery_app worker --pool=solo --loglevel=info
```

**3 — curl** (whitelisted domain `acme-supplies.com`; mock LLM defaults to `is_ap=true`)

```powershell
curl -s -X POST http://127.0.0.1:8000/ingest -H "Content-Type: application/json" -d "{\"thread_id\":\"t1\",\"message_id\":\"msg-demo-1\",\"from\":\"billing@acme-supplies.com\",\"subject\":\"Invoice INV-1\",\"body\":\"Please pay\"}"
```

202 `{ "task_id": "..." }`. After the worker runs:

```powershell
curl -s http://127.0.0.1:8000/health
```

Look up the ticket UUID printed in the worker log / result backend, or insert a known `message_id` and query pgAdmin. If Redis is down, POST runs the graph in-process and returns `{ "ticket_id", "status" }`.

```powershell
curl -s http://127.0.0.1:8000/tickets/<ticket-uuid>
```

Unknown domain (`evil.example`) → `quarantined` and triage does not run.

Plans: [docs/README.md](docs/README.md).
