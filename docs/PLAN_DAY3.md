# Day 3 — Full domain, seven ports, DB schema (~3–4h)

> Bring the hexagon to **assistant parity** (minus Streamlit). No new graph nodes except wiring that keeps Days 0–2 tests green.
>
> Reference: `p2p-ai-assistant/app/domain/`, `app/ports/`, `app/adapters/db_models.py`, `postgres_repos.py`, `app/api/deps.py`.
>
> Previous: [PLAN_DAY2.md](PLAN_DAY2.md). Next: [PLAN_DAY4.md](PLAN_DAY4.md). Charter: [README.md](README.md).

**Status:** closed — 7 ports, mocks + Postgres tickets/audit/drafts, `full_schema` migration. Next: [PLAN_DAY4.md](PLAN_DAY4.md).

Do **not** copy Launchpad `core/`. Do **not** implement Thread/Intent/Resolution nodes this day.

---

## 1. Domain — match assistant enums and models

Files: `app/domain/enums.py`, `models.py`, `events.py`, `deps.py`, `schemas.py` (LLM outputs can stay thin until Day 4–5).

- [x] `TicketStatus`: `open`, `awaiting_human`, `awaiting_sender_reply`, `resolved`, `escalated`, `quarantined`, `discarded`, `delegated`
- [x] `Intent`, `SenderType`, `InvoiceStage`, `InvoiceStatus`, `InvoiceMatchResult`, `DraftTarget`, `HumanReviewAction`, `AuditAction`
- [x] Models: `Sender`, `RoutingRule`, `Ticket` (full fields), `Invoice`, `ResponseDraft`, `AuditEntry`, `HumanReview`
- [x] Ticket fields: `intent`, `language`, `assigned_operator_id`, `confidence`, `is_thread_continuation` (kept `is_ap`)
- [x] `WorkflowDeps`: `settings`, `llm`, `email`, `tickets`, `sap`, `audit`, `senders`, `drafts`

Graph state (`app/graph/state.py`) may grow later (Days 4–5) toward `ProcessingContext` fields. This day: types exist; **still no `deps` in state**.

Tests: extend `tests/test_domain.py` for new enums/models (round-trip, required fields).

---

## 2. Ports

| Port | Assistant file | Lab file | Methods to match |
|---|---|---|---|
| `EmailPort` | `email_port.py` | already exists | `parse_webhook` |
| `TicketStorePort` | `invoice_store_port.py` | extend | `get_by_id`, `get_by_message_id`, `list_by_thread_id`, `list_tickets`, `save_ticket`, `count_by_status` (as needed by API) |
| `LLMPort` | `llm_port.py` | already exists | `generate` |
| `SAPPort` | `sap_port.py` | new | `get_approval_invoices`, `get_posted_invoices`, clearing/payment lookups as in mock |
| `AuditPort` | `audit_port.py` | new | `append`, `get_by_ticket_id` |
| `SenderDirectoryPort` | `sender_directory_port.py` | new | `get_by_email`, `get_by_domain`, routing-rule lookup as in assistant |
| `DraftPort` | `draft_port.py` | new | `save`, `get_by_ticket_id` |

Human reviews can live on a small repo (assistant: `HumanReviewRepo`) even if you do not add a dedicated port — match `HitlService` needs.

---

## 3. Adapters

- [x] `MockSAPAdapter` — `fixtures/sap_mock/` (lab copy; replace from assistant if you have it)
- [x] `MockSenderDirectory` — `fixtures/senders/`
- [x] In-memory: tickets, audit, drafts
- [x] SQLModel tables: `tickets` extra columns, `senders`, `routing_rules`, `invoice_cache`, `response_drafts`, `audit_entries`, `human_reviews`
- [x] Postgres repos: `TicketRepo`, `AuditRepo`, `DraftRepo`, `HumanReviewRepo`

Optional:

- [ ] `OpenAILLMAdapter` behind `LLMPort` if `LLM_PRIMARY_API_KEY` is set; else keep `MockLLMAdapter`

Wiring: `build_workflow_deps(session)` returns all **seven** ports.

---

## 4. Alembic — second migration

- [x] `alembic revision` `a1b2c3d4e5f6_full_schema.py`
- [x] Ticket extra columns: `intent`, `language`, `assigned_operator_id`, `confidence`, `is_thread_continuation`
- [x] New tables + FKs `ticket_id` / `draft_id`
- [x] Unique `message_id` retained
- [x] `alembic upgrade head`
- [x] Note in [ALEMBIC_PGADMIN.md](ALEMBIC_PGADMIN.md)

Gate: pytest against Postgres for ticket extra fields + audit append/get (compose up).

---

## 5. Fixtures and settings

- [x] Lab fixtures under `fixtures/` (`sap_mock/`, `senders/`); replace from assistant if available
- [x] Settings already on lab `settings.py` are canonical (`CONFIDENCE_THRESHOLD`, `NEAR_DUE_DAYS`, …)

Day 7 will add `RESOLUTION_RETRY_MIN_CONFIDENCE` (and optional retry cap). **Do not** add the retry loop this day.

---

## Definition of Done — Day 3

- [x] `WorkflowDeps` has 7 ports; `build_workflow_deps` wires mocks + Postgres tickets/audit/drafts
- [x] Second migration applied; pgAdmin shows new tables
- [x] Day 1–2 tests still pass (ticket extras have defaults)
- [x] No Streamlit, no new graph nodes required
- [x] Fixtures present under this repo (or documented relative path)

---

## Out of scope

Thread, Intent, SenderId, Routing, Resolution, Draft, HITL, Send nodes. Eval harness. Correction loop (Day 7).
