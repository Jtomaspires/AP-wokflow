# Day 2 — LangGraph (ingest → security → triage) + queue (~3–4h, by hand)

> Replace `TicketWorkflow` with **LangGraph**. Same logic as the first three “useful” P2P nodes, **without** Thread.
>
> Write the nodes yourself. Open `ingestion.py` / `security.py` / `triage.py` in P2P, understand the paths, reimplement as `(state) -> dict` updates.
>
> After this day: [PLAN_DAY3.md](PLAN_DAY3.md) expands domain/ports. Do **not** add Intent here. Charter: [README.md](README.md).

**Status:** closed — LangGraph 3 nodes + Celery + FastAPI (`POST /ingest`). Next: [PLAN_DAY3.md](PLAN_DAY3.md).

HTTP on this day may use `POST /ingest`. Day 5 aligns routes with the assistant (`POST /webhook/mock` plus HITL). Sync fallback if Redis is down is optional here (P2P `app/api/main.py` idea) and required for assistant parity later.

---

## Graph

```
START → ingest → security → triage → END
              ↘ stop (missing ids / duplicate)
                    ↘ stop (quarantine)
                          ↘ stop (discard)  or  END with ticket OPEN
```

LangGraph: `add_conditional_edges` when `should_stop` (or terminal status). Do not copy `BaseRouter`.

State (`app/graph/state.py`): `raw_payload`, `ticket_id`, `should_stop`, `stop_reason`. **Do not** put `deps` in state (it does not serialize well) — `make_*_node(deps)` / `build_graph(deps)` close `deps` in the node functions.

---

## Node 1 — Ingest (`app/graph/nodes/ingest.py`)

Reference: `p2p-ai-assistant/app/workflow/nodes/ingestion.py`

- [x] `deps.email.parse_webhook(raw_payload)` → `IncomingEmail`
- [x] Missing `message_id` or `thread_id` → `should_stop=True`, **do not** create a ticket
- [x] `get_by_message_id` → duplicate → stop, reuse existing ticket
- [x] Else: build `Ticket(status=open)`, `save_ticket`
- [x] Return state update with `ticket_id` / `stop_reason`

Tests (`tests/test_node_ingest.py`) with **memory store** + mock email:

- [x] valid payload → OPEN ticket in the store
- [x] same `message_id` twice → no second ticket
- [x] missing `thread_id` → stop

---

## Node 2 — Security (`app/graph/nodes/security.py`)

Reference: `security.py` in P2P. **Reduced** version is accepted on Day 2:

- [x] If `SECURITY_CHECK_ENABLED=False` → pass, ticket stays OPEN
- [x] Extract domain from ticket `sender_email`
- [x] If domain is **not** in `SENDER_DOMAIN_WHITELIST` → `status=quarantined`, `save_ticket`, `should_stop=True`
- [x] Otherwise → continue to triage
- [x] SPF/DKIM: **not** this day — whitelist only (`app/graph/nodes/security.py`)

Tests (`tests/test_node_security.py`):

- [x] domain on whitelist → continue, ticket OPEN
- [x] domain off-list + flag on → QUARANTINED, stop
- [x] flag off → pass even if off-list

SPF/DKIM parity with the assistant is [PLAN_DAY4.md](PLAN_DAY4.md).

---

## Node 3 — Triage = first LLM (`app/graph/nodes/triage.py`)

Reference: `triage.py` + `TriageOutput` + prompts in `app/llm/prompts.py` (a short prompt in the node is fine).

- [x] Pydantic schema `TriageOutput`: `is_ap: bool`, `confidence: float` (`app/domain/schemas.py`)
- [x] `await deps.llm.generate(..., output_schema=TriageOutput)` — node is **async** (compiled graph uses `ainvoke`)
- [x] `not is_ap` and `confidence >= TRIAGE_DISCARD_MIN_CONFIDENCE` → `discarded`, save, stop
- [x] Else → ticket stays OPEN (`is_ap` stored on the ticket)

Tests (`tests/test_node_triage.py`):

- [x] `enqueue({"is_ap": False, "confidence": 0.9})` → DISCARDED
- [x] `is_ap True` → OPEN
- [x] `is_ap False` with low confidence → OPEN (do not discard)

**Do not** implement IntentNode (Day 4). On Day 2, triage still edges to **END**. Day 4 changes that to Intent.

---

## Compile the graph (`app/graph/app.py`)

- [x] `StateGraph(LabState)`
- [x] `add_node` ingest, security, triage
- [x] edges + conditionals on `should_stop`
- [x] `compile()`
- [x] `build_graph(deps) -> compiled graph`

Integration test **without Celery** (`tests/test_graph.py`):

- [x] ACME email (whitelisted domain) + mock LLM `is_ap=True` → ticket OPEN
- [x] unknown domain + security on → QUARANTINED, triage **does not** run (`llm.calls` empty)
- [x] AP false + high confidence → DISCARDED

---

## Celery (`app/worker/tasks.py`)

Same idea as P2P `process_email`, by hand:

- [x] `Celery` broker/backend = `REDIS_URL`
- [x] `process_email(raw_payload: dict)`:
  - `Session(engine)`
  - `deps = build_workflow_deps(session)`
  - `build_graph(deps).ainvoke(...)` (`asyncio.run` — triage is async)
  - return `{ticket_id, status}`
- [x] Windows worker: `--pool=solo` (see module docstring)

First run the task **synchronously** in a test (no `.delay`) against Postgres (`tests/test_process_email.py`). `run_process_email(..., llm=)` overrides the lab default mock (`is_ap=true` in `build_workflow_deps`).

---

## FastAPI (`app/api/main.py`)

- [x] `GET /health`
- [x] `POST /ingest`: body = P2P-style payload (`thread_id`, `message_id`, `from`/`from_email`, `subject`, `body`)
  - `process_email.delay(payload)` → 202 `{task_id}`
- [x] `GET /tickets/{id}` → Postgres repo
- [x] Sync fallback on POST if Redis/broker is down → 202 `{ticket_id, status}`

Root runbook + curl: [README.md](../README.md). Tests: `tests/test_api.py`.

Day 5 aligns with the assistant (`POST /webhook/mock` plus HITL).

---

## Definition of Done — Day 2

- [x] Path: POST `/ingest` → Redis → worker → three LangGraph nodes → `tickets` row (fallback: in-process if broker down)
- [x] Triage uses `LLMPort` (mock default `is_ap=true` in `build_workflow_deps`); the node does not import `openai`
- [x] Security needs no extra port (only `settings` + ticket store)
- [x] Root README: uvicorn, celery, example curl
- [x] **No** Intent, SAP, HITL, Streamlit on this day

---

## P2P ↔ lab (nodes)

| P2P | Lab (Day 2) |
|---|---|
| `IngestionNode.process` | `ingest` (LangGraph) |
| `SecurityNode.process` | `security` |
| `TriageNode.process` + `call_llm` | `triage` + `LLMPort` |
| `ThreadResolutionNode` | **omitted until Day 4** |
| `TicketWorkflow` + `core/` | `StateGraph` |

---

## If time remains (optional)

- Sync POST fallback if Redis is down
- `OpenAILLMAdapter` behind the same `LLMPort` — the triage node **does not change**
