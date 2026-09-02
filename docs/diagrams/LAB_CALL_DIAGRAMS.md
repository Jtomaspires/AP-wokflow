# Call diagrams — mini-lab (Days 0–2) and full spine (Days 3–6)

Mirror of `P2P/diagrams/P2P_AI_CALL_DIAGRAMS.md`. **No Streamlit.**

Paste each Mermaid block into [mermaid.live](https://mermaid.live), Notion, or diagrams.net → *Arrange → Insert → Advanced → Mermaid*.

`LAB_CALL_DIAGRAMS.drawio` has the same views (pages 1–3 = mini-lab; pages 4–6 = full spec).

---

## Days 0–2 — three ports, three nodes

### 1. Hexagonal architecture (mini-lab)

**Pitch:** the graph and domain do not import Postgres, Redis, or the LLM client. Traffic goes through **ports**; **adapters** swap (memory in tests, Postgres in the worker) without rewriting nodes.

```mermaid
flowchart LR
  subgraph IN["Driving adapters — inbound"]
    CURL["curl / TestClient"]
    API["FastAPI POST /ingest · GET /tickets/id"]
  end

  subgraph HEX["Core — vendor-agnostic"]
    M["IncomingEmail · Ticket · TicketStatus · WorkflowDeps"]
    WF["LangGraph ingest → security → triage"]
    PE["EmailPort"]
    PT["TicketStorePort"]
    PL["LLMPort"]
    M --> WF --> PE
    WF --> PT
    WF --> PL
  end

  subgraph OUT["Driven adapters — outbound"]
    EM["MockEmailAdapter"]
    LLM["MockLLMAdapter"]
    PG[("Postgres tickets Alembic")]
    MEM["InMemoryTicketStore tests"]
  end

  IN --> HEX --> OUT
```

FastAPI never talks to the LLM. Triage never imports `openai`. Ingest never imports SQLModel — only `TicketStorePort.save_ticket`.

### 2. LangGraph (3 nodes)

**Pitch:** a payload visits at most **three** nodes. Early exits: reject ingest, quarantine, discard. **No** Thread, Intent, HITL, or Send.

```mermaid
flowchart TD
  START([POST /ingest]) --> N1
  N1["Ingest EmailPort.parse_webhook Ticket OPEN"] --> N1D{ids ok and not duplicate?}
  N1D -->|no| REJ["STOP"]
  N1D -->|yes| N0
  N0["Security domain whitelist"] --> N0D{Sender accepted?}
  N0D -->|no| QUAR["STOP QUARANTINED"]
  N0D -->|yes| N2
  N2["Triage first LLM LLMPort"] --> N2D{AP?}
  N2D -->|no plus high conf| DISC["STOP DISCARDED"]
  N2D -->|yes or uncertain| OPEN["END ticket OPEN"]
```

Ingest and security are deterministic. Thread (assistant 1.5) **does not exist** until Day 4.

### 3. Runtime — request → queue → worker → DB

**Pitch:** LangGraph runs **inside** the worker, not in the FastAPI process (except sync fallback).

```mermaid
sequenceDiagram
  participant C as curl
  participant API as FastAPI
  participant R as Redis
  participant W as Celery worker
  participant G as LangGraph
  participant P as Postgres

  C->>API: POST /ingest payload
  API->>R: process_email.delay(payload)
  API-->>C: 202 accepted
  W->>R: pull task
  W->>G: ainvoke with WorkflowDeps
  G->>P: INSERT or UPDATE tickets
  C->>API: GET /tickets/id
  API->>P: TicketRepo.get_by_id
  API-->>C: status
```

If the worker is down: POST may still return 202; GET has no row until ingest runs. If `alembic upgrade` did not run: `save_ticket` fails.

---

## Days 3–6 — seven ports, full workflow, HITL via API

### 4. Hexagon (assistant parity, no Streamlit)

```mermaid
flowchart LR
  subgraph IN["Driving"]
    CURL2["curl / TestClient"]
    API2["FastAPI /webhook/mock /tickets approve escalate"]
  end

  subgraph HEX2["Core"]
    DOM["IncomingEmail Ticket Invoice Draft Sender"]
    WF2["LangGraph full spine plus HITL interrupt"]
    P1["EmailPort"]
    P2["TicketStorePort"]
    P3["LLMPort"]
    P4["SAPPort"]
    P5["AuditPort"]
    P6["SenderDirectoryPort"]
    P7["DraftPort"]
    DOM --> WF2
    WF2 --> P1
    WF2 --> P2
    WF2 --> P3
    WF2 --> P4
    WF2 --> P5
    WF2 --> P6
    WF2 --> P7
  end

  subgraph OUT2["Driven"]
    A1["MockEmail MockLLM optional OpenAI"]
    A2["MockSAP MockSenders"]
    A3[("Postgres tickets audit drafts reviews")]
  end

  IN --> HEX2 --> OUT2
```

### 5. Full LangGraph spine + HITL

Day 7 retry stays **inside** `resolution` (not extra graph nodes). Default eval has retry off.

```mermaid
flowchart TD
  START2([POST /webhook/mock]) --> ingest
  ingest -->|missing ids or duplicate| E1[END]
  ingest --> security
  security -->|quarantine| E2[END]
  security --> thread
  thread -->|continuation| resolution
  thread -->|new thread| triage
  triage -->|discard| E3[END]
  triage --> intent
  intent -->|unknown or low conf| resolution
  intent --> sender
  sender --> routing
  routing -->|DELEGATE| E4[END]
  routing -->|MINE| resolution
  resolution --> draft
  draft --> hitl
  hitl -->|AWAITING_HUMAN interrupt| wait[Wait for API]
  wait -->|POST approve| send
  wait -->|POST escalate| E5[END]
  send --> E6[END]
```

### 6. Sequence — webhook through approve

```mermaid
sequenceDiagram
  participant C as curl
  participant API as FastAPI
  participant R as Redis
  participant W as Celery worker
  participant G as LangGraph
  participant P as Postgres

  C->>API: POST /webhook/mock
  API->>R: process_email.delay
  API-->>C: 202 task_id
  W->>G: ainvoke inbound graph
  G->>P: tickets audit drafts
  G-->>W: stop at HITL AWAITING_HUMAN
  C->>API: GET /tickets/id
  API->>P: ticket plus draft plus audit
  API-->>C: AWAITING_HUMAN
  C->>API: POST /tickets/id/approve
  API->>G: resume send node
  G->>P: RESOLVED HumanReview
  API-->>C: ticket resolved
```

Escalate skips send and writes `ESCALATED`.

---

## Spec → code map

| Step | Assistant | This repo |
|---|---|---|
| Ingest | `IngestionNode` | `app/graph/nodes/ingest.py` |
| Security | `SecurityNode` | `app/graph/nodes/security.py` |
| Thread | `ThreadResolutionNode` | `app/graph/nodes/thread.py` (Day 4) |
| Triage | `TriageNode` | `app/graph/nodes/triage.py` |
| Intent | `IntentNode` | `app/graph/nodes/intent.py` (Day 4) |
| Sender / Routing | `SenderIdNode` / `RoutingNode` | Day 4 nodes |
| Resolution / Draft / HITL / Send | matching node files | Days 5–7 |
| Graph | `TicketWorkflow` | `StateGraph` in `app/graph/app.py` |
| Queue | `process_email.delay` | `app/worker/tasks.py` |
| HITL HTTP | `app/api/hitl.py` + tickets | Day 5 — **no Streamlit** |
| Ports | 7 | 3 until Day 3; then 7 |

---

## What diagrams still omit

Streamlit, OCR, live Nylas/SAP, auto-send. Day 7 retry is an internal loop in Resolution, not a separate box unless you expand the resolution node in a talk.
