# Day 1 — Domain, ports, adapters, Alembic (~3h, by hand)

> Mini-lab goal: the **same shape** as P2P (`domain` → `ports` → `adapters`), only what Ingest + Security + Triage need.
>
> Reference (read, do not paste whole files): `p2p-ai-assistant/app/domain/`, `app/ports/`, `app/adapters/mock_*.py`, `app/adapters/postgres_repos.py` (tickets only).
>
> Full domain + 7 ports = [PLAN_DAY3.md](PLAN_DAY3.md). Charter: [README.md](README.md).

**Status:** closed — domain, 3 ports, adapters, Alembic, Gates 1–3, wiring. LangGraph / Celery = Day 2.

---

## 1. Domain (~40 min)

Minimal enums (`app/domain/enums.py`):

- [x] `TicketStatus`: `open`, `quarantined`, `discarded`  
  (no `awaiting_human`, `delegated`, etc. until Day 3)

Inbound event (`app/domain/events.py`) — mirror P2P:

- [x] `IncomingEmail`: `thread_id`, `message_id`, `from_email`, `subject`, `body`, `received_at`, `attachments` (simple list), optional `spf_pass` / `dkim_pass`

Persisted ticket (`app/domain/models.py`) — subset:

- [x] `id` UUID, `thread_id`, `message_id`, `sender_email`, `subject`, `body`, `received_at`, `status`, `created_at`, `updated_at`
- [x] No `intent` / `assigned_operator_id` / thread flags yet — `is_ap: bool | None` included for triage

Deps (`app/domain/deps.py`):

- [x] Dataclass `WorkflowDeps`: `settings`, `email`, `tickets`, `llm`  
  (no sap, senders, drafts, audit — Day 3)

LangGraph **state is not this day** — that is Day 2. Today: domain types and I/O.

### Gate 1

```bash
pytest tests/test_domain.py -v
```

- [x] Enums `.value`
- [x] `IncomingEmail` / `Ticket` validate; ticket rejects missing `thread_id`
- [x] Pydantic round-trip
- [x] `pytest tests/test_domain.py -v` — 7 passed

---

## 2. Ports (~25 min)

ABCs in `app/ports/`. Signatures aligned with P2P; you may name tickets `TicketStorePort` instead of `InvoiceStorePort`.

- [x] `EmailPort.parse_webhook(payload: dict) -> IncomingEmail`
- [x] `TicketStorePort`: `get_by_id`, `get_by_message_id`, `save_ticket`  
  (`list_by_thread_id` **not** required until ThreadNode / Day 4)
- [x] `LLMPort.generate(*, system_prompt, user_prompt, output_schema: type[BaseModel]) -> BaseModel`  
  (same as P2P; the mock validates a dict against the schema)

No adapter talks to LangGraph yet.

---

## 3. Adapters (~50 min)

Write **small** implementations:

| Adapter | Role | Look at in P2P |
|---|---|---|
| `mock_email.py` | `from` / `from_email`, subject, body → `IncomingEmail` | `mock_email.py` |
| `mock_llm.py` | queue of dicts → `output_schema.model_validate` | `mock_llm.py` |
| `memory_ticket_store.py` | in-memory dict for node tests | `memory_ticket_store.py` |
| `db_models.py` | `TicketTable` SQLModel `table=True` | `db_models.py` (tickets only) |
| `postgres_tickets.py` | `TicketRepo` with `Session` | `postgres_repos.TicketRepo` (methods you need) |

- [x] Mock LLM: `enqueue({...})`; empty queue → clear error
- [x] Do not implement `OpenAILLMAdapter` this day (optional Day 2 / Day 3 if you have a key)

### Gate 2 — mocks + memory

```bash
pytest tests/test_adapters.py -v
```

- `parse_webhook` maps `from` → `from_email`
- `MockLLMAdapter` returns a `TriageOutput` (`is_ap: bool`, `confidence: float`)
- Memory store: save + get_by_message_id
- [x] `pytest tests/test_adapters.py -v` — 4 passed

---

## 4. Alembic (~40 min)

- [x] `alembic init alembic` (`alembic/` + `alembic.ini`)
- [x] `env.py` imports `app.adapters.db_models` and uses `target_metadata = SQLModel.metadata`
- [x] `env.py` uses `settings.DATABASE_URL` (`config.set_main_option("sqlalchemy.url", ...)`)
- [x] `alembic revision --autogenerate -m "tickets"` → `alembic/versions/edb81d2a0b75_tickets.py`
- [x] **Read** the migration: table `tickets`, unique index on `message_id`
- [x] `alembic upgrade head` (`Running upgrade  -> edb81d2a0b75, tickets`)
- [x] Confirm `tickets` in pgAdmin (`lab` at `127.0.0.1:5434`) — see [ALEMBIC_PGADMIN.md](ALEMBIC_PGADMIN.md)

### Gate 3 — Postgres repo

```bash
pytest tests/test_ticket_repo.py -v
```

- save + get_by_id on the real DB (compose)
- [x] `pytest tests/test_ticket_repo.py -v` — 1 passed

---

## 5. Wiring (10 min)

- [x] `build_workflow_deps(session)` in `app/api/deps.py`:  
  `MockEmailAdapter`, `TicketRepo(session)`, `MockLLMAdapter`, `settings`

Still **do not** wire Celery (Day 2).

---

## Definition of Done — Day 1

- [x] Minimal hexagon: 3 ports, mocks + Postgres tickets
- [x] `tickets` table created by Alembic
- [x] **No** LangGraph files yet (Day 2)
- [x] Written by you, P2P open beside you as a guide only

---

## Out of scope for this day

`ThreadResolutionNode`, Intent, Sender, SAP, drafts, Launchpad `core/`, copying all of `postgres_repos.py`. Those land in Days 3–5.
