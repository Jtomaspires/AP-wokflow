# P2P AI LangGraph — technical spec (parity with p2p-ai-assistant)

This repo rebuilds **`p2p-ai-assistant`** with **native LangGraph** instead of Launchpad `TicketWorkflow` / `core/`.

Days **0–2** were a **mini-lab** (ingest → security → triage). Days **3–6** match the assistant technical spec. Day **7** is **post-parity** (resolution retry + visual root README). Later work adds a real LLM adapter, cookie sessions, and the operator console in [`frontend/`](../frontend/).

**Streamlit is out of scope.** Operators use FastAPI (curl) or the Vite console.

## How to work

- `p2p-ai-assistant` is **reference only**: read a node, reimplement as LangGraph `(state) -> dict` + `StateGraph`. Do **not** copy `TicketWorkflow` or `app/workflow/core/`.
- Close `WorkflowDeps` in node factories. **Never** put `deps` in graph state (it does not serialize).
- Behaviour source of truth: **current assistant code**, not unimplemented parent-spec items (OCR, live SAP, auto-send). Nylas inbound and Approve send are in this repo.

## Target graph

```
START → ingest → security → thread ─┬─ escalated_thread → END
                                    ├─ continuation → resolution → draft → hitl → END (AWAITING_HUMAN)
                                    └─ new → triage ─┬─ discard → END
                                                     └─ intent ─┬─ skip identity → resolution → …
                                                                └─ sender → routing ─┬─ DELEGATE → END
                                                                                     └─ MINE → resolution → draft → hitl → END
HITL: HitlService.approve → send → RESOLVED (mock, or Nylas when flag + key + grant) | send_failed stays AWAITING_HUMAN | escalate → ESCALATED (no send)
```

HITL is **option 2** (documented in `app/graph/app.py`): inbound graph **ends at hitl**; Celery does not resume a checkpointer. Day 7 retry, if enabled, stays **inside** the resolution node (`RESOLUTION_RETRY_ENABLED`, default **false** so Day 6 eval is unchanged).

## What is in vs out

| In | Out |
|---|---|
| Full spine in LangGraph (nodes 0–8 + Send after approve) | Streamlit |
| FastAPI: `/webhook/mock`, `/webhook/nylas`, tickets, approve/escalate, `/auth`. Approve sends when `NYLAS_SEND_ENABLED` plus key and grant are set | Nylas SDK and an OAuth server in this repo |
| Cookie sessions (Argon2, `HttpOnly`, SHA-256 in Postgres). Auth is **not** a workflow port | Roles, password reset, sign-up, OAuth |
| React console: login, status tiles, ticket feed, tabbed detail, HITL dialog | Live SAP (`MockSAPAdapter` + fixtures) |
| Celery + Redis | OCR / PDF pipeline |
| Alembic: tickets, audit, drafts, human_reviews, senders, routing_rules, invoice_cache, operators, operator_sessions | Auto-send via `CONFIDENCE_THRESHOLD` |
| 7 ports: Email, Tickets, LLM, SAP, Audit, Senders, Drafts | Copying Launchpad `core/` / `WorkflowRegistry` |
| `OpenAILLMAdapter` when `LLM_PRIMARY_API_KEY` is set; otherwise `MockLLMAdapter`. Draft prompt includes invoice facts | LangGraph `interrupt()` + checkpointer |
| Eval / golden fixtures 001–030. Checked-in baseline 29/30; 022 fails on purpose (fresh store per fixture) | |

## Plans

Day-by-day files are a **historical log** (do not rewrite them to match later UI). Current behaviour is this page + the [root README](../README.md).

| Day | File | Focus | Status |
|---|---|---|---|
| 0 | [PLAN_DAY0.md](PLAN_DAY0.md) | Scaffold, Docker, settings | Done (mini-lab) |
| 1 | [PLAN_DAY1.md](PLAN_DAY1.md) | Domain + 3 ports + adapters + Alembic tickets | Done (mini-lab) |
| 2 | [PLAN_DAY2.md](PLAN_DAY2.md) | LangGraph 3 nodes + Celery + FastAPI | Done (mini-lab) |
| 3 | [PLAN_DAY3.md](PLAN_DAY3.md) | Full domain, 7 ports, schema, fixtures | Done |
| 4 | [PLAN_DAY4.md](PLAN_DAY4.md) | Thread, intent, sender, routing, SPF/DKIM, audit | Done |
| 5 | [PLAN_DAY5.md](PLAN_DAY5.md) | Resolution (parity), draft, HITL, send, HITL API | Done |
| 6 | [PLAN_DAY6.md](PLAN_DAY6.md) | Eval / shadow via `ainvoke` | Done |
| 7 | [PLAN_DAY7.md](PLAN_DAY7.md) | Resolution retry loop + visual README | Done (post-parity) |
| 8 | [PLAN_DAY8.md](PLAN_DAY8.md) | OpenAI adapter, invoice facts in the draft prompt, token draft judge | Done |
| 9 | [PLAN_DAY9.md](PLAN_DAY9.md) | Operators, cookie sessions, protected ticket and HITL routes | Done |
| 10 | [PLAN_DAY10.md](PLAN_DAY10.md) | shadcn operator console | Done |
| 11 | [PLAN_DAY11.md](PLAN_DAY11.md) | Login page and session operator in the UI | Done |
| 12 | [PLAN_DAY12.md](PLAN_DAY12.md) | Six workflow fixes: content-hash duplicate, SPF/DKIM penalty, thread truncation, extraction confidence, no-rule routing, HITL deadline | Done |
| 13 | [PLAN_DAY13.md](PLAN_DAY13.md) | Nylas inbound webhook, and Approve sends the draft through that grant | Implemented |

Alembic + pgAdmin (lab DB on port **5434**): [ALEMBIC_PGADMIN.md](ALEMBIC_PGADMIN.md). Operator UI: [`frontend/README.md`](../frontend/README.md). What an operator does with a ticket: [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md). Test inventory and gaps (pytest, eval, frontend, CI): [TEST_GAPS.md](TEST_GAPS.md). Mock email fixtures and expected outcomes: [EMAIL_FIXTURES.md](EMAIL_FIXTURES.md). Live run results: [EMAIL_FIXTURES_LIVE_RUN.md](EMAIL_FIXTURES_LIVE_RUN.md). Lab walkthrough: [Demo.md](Demo.md).

## LangGraph mapping (locked)

| Assistant | This repo |
|---|---|
| `TicketWorkflow` + `core/` | `StateGraph` in `app/graph/app.py` |
| `Node.process(context)` / `BaseRouter` | `make_*_node(deps)` + `add_conditional_edges` |
| `ProcessingContext` | Graph state (IDs + routing fields; heavy objects in DB) |
| `HitlNode` stop + `HitlService` → `SendNode` | Graph ends at hitl; `HitlService.approve` runs `make_send_node` |
| `POST /webhook/mock` → `process_email.delay` | Same routes (and lab `/ingest`). Ticket and HITL routes require the session cookie |
| Approve body `{ operator_id }` | Approve body is `{ final_text? }`. `operator_id` comes from the session |
| `build_workflow_deps` (7 ports) | Same pattern |

## Assistant reference (read only)

| Piece | Path in `p2p-ai-assistant` |
|---|---|
| Event / ticket / enums | `app/domain/events.py`, `models.py`, `enums.py`, `context.py` |
| Ports | `app/ports/` |
| Wiring | `app/api/deps.py` |
| Queue | `app/api/main.py`, `app/workflow/tasks.py` |
| Nodes 0–8 | `app/workflow/nodes/` |
| HITL API | `app/api/hitl.py`, `app/api/tickets.py` |
| Eval | `scripts/eval_harness.py`, `fixtures/emails/` |

## Diagrams

- [diagrams/LAB_CALL_DIAGRAMS.md](diagrams/LAB_CALL_DIAGRAMS.md) — workflow, seven-port architecture, Redis and Celery queue, outcome per email type
- [diagrams/LAB_CALL_DIAGRAMS.drawio](diagrams/LAB_CALL_DIAGRAMS.drawio) — the same four pages in diagrams.net
- [assets/architecture.svg](assets/architecture.svg) / [assets/happy-path.gif](assets/happy-path.gif) — root README visuals
