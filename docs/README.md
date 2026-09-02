# P2P AI LangGraph — technical spec (parity with p2p-ai-assistant)

This repo rebuilds **`p2p-ai-assistant`** with **native LangGraph** instead of Launchpad `TicketWorkflow` / `core/`.

Days **0–2** were a **mini-lab** (ingest → security → triage). Days **3–6** bring the lab to **the same technical spec** as the assistant. Day **7** is **post-parity** (features the original product does not have).

**Streamlit is out of scope.** Operators use FastAPI (curl / any HTTP client).

## How to work

- `p2p-ai-assistant` is **reference only**: read a node, reimplement as LangGraph `(state) -> dict` + `StateGraph`. Do **not** copy `TicketWorkflow` or `app/workflow/core/`.
- Close `WorkflowDeps` in node factories. **Never** put `deps` in graph state (it does not serialize).
- Behaviour source of truth: **current assistant code**, not unimplemented parent-spec items (OCR, live Nylas, live SAP, auto-send).

## Target graph (Days 3–6)

```
START → ingest → security → thread ─┬─ continuation → resolution → draft → hitl ─ interrupt
                                    └─ new → triage ─┬─ discard → END
                                                     └─ intent ─┬─ skip identity → resolution → …
                                                                └─ sender → routing ─┬─ DELEGATE → END
                                                                                     └─ MINE → resolution → draft → hitl
HITL resume: approve → send → END | escalate → END
```

Day 7 may **retry inside resolution** before HITL; that loop is not part of Days 3–6.

## What is in vs out

| In | Out |
|---|---|
| Full spine in LangGraph (nodes 0–8 + Send on HITL resume) | Streamlit dashboard |
| FastAPI: `/webhook/mock`, tickets, approve/escalate | Live Nylas webhook/send (flag + mock only) |
| Celery + Redis | Live SAP (`MockSAPAdapter` + fixtures) |
| Alembic: tickets, audit, drafts, human_reviews, senders, routing_rules, invoice_cache | OCR / PDF pipeline |
| 7 ports: Email, Tickets, LLM, SAP, Audit, Senders, Drafts | Auto-send via `CONFIDENCE_THRESHOLD` |
| Mock + Postgres adapters; optional OpenAI behind `LLMPort` | Copying Launchpad `core/` / `WorkflowRegistry` |
| Eval / golden fixtures 001–020 (Day 6) | |

## Plans

| Day | File | Focus | Status |
|---|---|---|---|
| 0 | [PLAN_DAY0.md](PLAN_DAY0.md) | Scaffold, Docker, settings | Done (mini-lab) |
| 1 | [PLAN_DAY1.md](PLAN_DAY1.md) | Domain + 3 ports + adapters + Alembic tickets | Done (mini-lab) |
| 2 | [PLAN_DAY2.md](PLAN_DAY2.md) | LangGraph 3 nodes + Celery + FastAPI | Done (mini-lab) |
| 3 | [PLAN_DAY3.md](PLAN_DAY3.md) | Full domain, 7 ports, schema, fixtures | Planned |
| 4 | [PLAN_DAY4.md](PLAN_DAY4.md) | Thread, intent, sender, routing, SPF/DKIM, audit | Planned |
| 5 | [PLAN_DAY5.md](PLAN_DAY5.md) | Resolution (parity), draft, HITL, send, HITL API | Planned |
| 6 | [PLAN_DAY6.md](PLAN_DAY6.md) | Eval / shadow via `ainvoke` | Planned |
| 7 | [PLAN_DAY7.md](PLAN_DAY7.md) | Resolution retry loop + visual README | Planned (post-parity) |

Alembic + pgAdmin (lab DB on port **5434**): [ALEMBIC_PGADMIN.md](ALEMBIC_PGADMIN.md).

## LangGraph mapping (locked)

| Assistant | This repo |
|---|---|
| `TicketWorkflow` + `core/` | `StateGraph` in `app/graph/app.py` |
| `Node.process(context)` / `BaseRouter` | `make_*_node(deps)` + `add_conditional_edges` |
| `ProcessingContext` | Graph state (IDs + routing fields; heavy objects in DB) |
| `HitlNode` stop + `HitlService` → `SendNode` | `interrupt()` / resume **or** same stop + re-entry; same operator API |
| `POST /webhook/mock` → `process_email.delay` | Same routes (not only lab `/ingest`) |
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

- [diagrams/LAB_CALL_DIAGRAMS.md](diagrams/LAB_CALL_DIAGRAMS.md) — 7-port hexagon, full graph + HITL, API sequence
- [diagrams/LAB_CALL_DIAGRAMS.drawio](diagrams/LAB_CALL_DIAGRAMS.drawio) — same views in diagrams.net

Mini-lab (Days 0–2) diagrams remain as the **first three pages** of the draw.io file; full-spine views are additional pages.
