# Day 3 — Full domain, seven ports, DB schema (~3–4h)

> Bring the hexagon to **assistant parity** (minus Streamlit). No new graph nodes except wiring that keeps Days 0–2 tests green.
>
> Reference: `p2p-ai-assistant/app/domain/`, `app/ports/`, `app/adapters/db_models.py`, `postgres_repos.py`, `app/api/deps.py`.
>
> Previous: [PLAN_DAY2.md](PLAN_DAY2.md). Next: [PLAN_DAY4.md](PLAN_DAY4.md). Charter: [README.md](README.md).

**Status:** planned.

Do **not** copy Launchpad `core/`. Do **not** implement Thread/Intent/Resolution nodes this day.

---

## 1. Domain — match assistant enums and models

Files: `app/domain/enums.py`, `models.py`, `events.py`, `deps.py`, `schemas.py` (LLM outputs can stay thin until Day 4–5).

- [ ] `TicketStatus`: `open`, `awaiting_human`, `awaiting_sender_reply`, `resolved`, `escalated`, `quarantined`, `discarded`, `delegated`
- [ ] `Intent`, `SenderType`, `InvoiceStage`, `InvoiceStatus`, `InvoiceMatchResult`, `DraftTarget`, `HumanReviewAction`, `AuditAction` — same string values as assistant `app/domain/enums.py`
- [ ] Models: `Sender`, `RoutingRule`, `Ticket` (full fields), `Invoice`, `ResponseDraft`, `AuditEntry`, `HumanReview`
- [ ] Ticket fields the mini-lab skipped: `intent`, `language`, `assigned_operator_id`, `confidence`, `is_thread_continuation` (keep `is_ap` if already used)
- [ ] `WorkflowDeps`: `settings`, `llm`, `email`, `tickets`, `sap`, `audit`, `senders`, `drafts`

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

- [ ] `MockSAPAdapter` — load `fixtures/sap_mock/` (copy or symlink from assistant; **do not regenerate**)
- [ ] `MockSenderDirectory` — load `fixtures/senders/`
- [ ] In-memory: tickets (already), plus audit, drafts for unit tests
- [ ] SQLModel tables matching assistant `app/adapters/db_models.py`:  
  `tickets` (extra columns), `senders`, `routing_rules`, `invoice_cache`, `response_drafts`, `audit_entries`, `human_reviews`
- [ ] Postgres repos: `TicketRepo`, `AuditRepo`, `DraftRepo`, `HumanReviewRepo` (and sender/invoice if you persist them; assistant runtime still uses **fixture JSON** for senders/SAP)

Optional:

- [ ] `OpenAILLMAdapter` behind `LLMPort` if `LLM_PRIMARY_API_KEY` is set; else keep `MockLLMAdapter`

Wiring: `build_workflow_deps(session)` returns all **seven** ports.

---

## 4. Alembic — second migration

- [ ] `alembic revision --autogenerate -m "full_schema"` (or equivalent)
- [ ] Ticket extra columns: `intent`, `language`, `assigned_operator_id`, `confidence`, `is_thread_continuation`
- [ ] New tables as above; FKs `ticket_id` / `draft_id` like assistant
- [ ] Unique `message_id` retained
- [ ] `alembic upgrade head`
- [ ] Note in [ALEMBIC_PGADMIN.md](ALEMBIC_PGADMIN.md): extra tables visible in `lab` on **5434**

Gate: pytest against Postgres for ticket extra fields + audit append/get (compose up).

---

## 5. Fixtures and settings

- [ ] Copy/link `p2p-ai-assistant/fixtures/` (`emails/`, `sap_mock/`, `senders/`, invoices if referenced)
- [ ] Settings already on lab `settings.py` become **canonical**: `CONFIDENCE_THRESHOLD`, `NEAR_DUE_DAYS`, `VAT_RATE`, `MATCH_VALUE_TOLERANCE_PCT` / `ABS`, `DEFAULT_OPERATOR_ID`, `INVOICING_EMAIL`, `PAYMENTS_EMAIL`, `NYLAS_SEND_ENABLED`, `SPF_DKIM_ENABLED`, `INTENT_MIN_CONFIDENCE`, LLM timeouts

Day 7 will add `RESOLUTION_RETRY_MIN_CONFIDENCE` (and optional retry cap). **Do not** add the retry loop this day.

---

## Definition of Done — Day 3

- [ ] `WorkflowDeps` has 7 ports; `build_workflow_deps` wires mocks + Postgres tickets/audit/drafts
- [ ] Second migration applied; pgAdmin shows new tables
- [ ] Day 1–2 tests still pass (adapt ticket model/status if needed)
- [ ] No Streamlit, no new graph nodes required
- [ ] Fixtures present under this repo (or documented relative path)

---

## Out of scope

Thread, Intent, SenderId, Routing, Resolution, Draft, HITL, Send nodes. Eval harness. Correction loop (Day 7).
