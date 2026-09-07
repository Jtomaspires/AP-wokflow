# p2p-ai-langraph

LangGraph rebuild of a procure-to-pay AP email assistant. Operators use **HTTP** (curl or any client). There is **no Streamlit UI**.

Inbound mail is classified, matched against mock SAP invoices, drafted, and parked for a human. Send runs only after `POST /tickets/{id}/approve`.

![Architecture: HTTP and Celery drive a seven-port LangGraph hexagon; HITL approve calls send](docs/assets/architecture.svg)

Call-level diagrams (Mermaid / draw.io): [docs/diagrams/LAB_CALL_DIAGRAMS.md](docs/diagrams/LAB_CALL_DIAGRAMS.md). Day plans: [docs/README.md](docs/README.md).

## Happy path

Webhook → inbound graph → `AWAITING_HUMAN` → approve → mock send.

![Happy path: webhook, graph, HITL, approve, send](docs/assets/happy-path.gif)

```
START → ingest → security → thread → triage → intent → sender → routing
      → resolution → draft → hitl → END
approve → send → RESOLVED     |     escalate → ESCALATED (no send)
```

Resolution can retry **once** with wider match tolerances when `RESOLUTION_RETRY_ENABLED=true`. Default is **off** so Day 6 eval stays comparable to the original assistant.

## Run

Postgres **5434**, Redis **6380**. From this directory:

```powershell
docker compose up -d
copy .env.dev .env
alembic upgrade head
```

Fix `DATABASE_URL` in `.env` to `lab:lab_dev` if compose uses those credentials.

**API**

```powershell
uvicorn app.api.main:app --reload --port 8000
```

**Worker (Windows: `--pool=solo`)**

```powershell
celery -A app.worker.tasks:celery_app worker --pool=solo --loglevel=info
```

**Ingest** (whitelisted domain `acme-supplies.com`; mock LLM defaults to AP + INV-2026-0001):

```powershell
curl -s -X POST http://127.0.0.1:8000/webhook/mock -H "Content-Type: application/json" -d "{\"thread_id\":\"t1\",\"message_id\":\"msg-demo-1\",\"from\":\"billing@acme-supplies.com\",\"subject\":\"Invoice INV-2026-0001\",\"body\":\"Please confirm payment status\"}"
```

If Redis is down, the same POST runs the graph in-process and returns `{ "ticket_id", "status" }`.

```powershell
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/tickets/<ticket-uuid>
curl -s -X POST http://127.0.0.1:8000/tickets/<ticket-uuid>/approve -H "Content-Type: application/json" -d "{\"operator_id\":\"op_joao\"}"
```

Unknown domain (`evil.example`) → `quarantined`. High-confidence non-AP → `discarded`. Other operator → `delegated`. Never auto-send.

**Eval** (in-memory LangGraph, fixture-guided LLM, retry off):

```powershell
python scripts/run_eval.py
```

Writes `golden_dataset/baselines/v1.json` and exits 1 if workflow success &lt; 0.80.

## What is in vs out

| In | Out |
|---|---|
| Native LangGraph, seven ports, FastAPI HITL | Streamlit |
| Mock SAP / senders / LLM, Celery + Postgres | Live Nylas, live SAP, OCR |
| Optional resolution retry (flagged) | Auto-send via `CONFIDENCE_THRESHOLD` |
