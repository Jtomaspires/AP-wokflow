# Day 5 — Resolution → Draft → HITL → Send + HITL API

> **Parity only** with assistant invoice matching, draft decision table, always-HITL, and HTTP HITL. No resolution retry loop (that is [PLAN_DAY7.md](PLAN_DAY7.md)).
>
> Reference: `resolution.py`, `draft.py`, `hitl.py`, `send.py`, `app/api/hitl.py`, `app/api/tickets.py`, `app/api/main.py`, `tests/test_node_resolution.py`, `tests/test_dashboard_api.py` (API only — ignore Streamlit).
>
> Previous: [PLAN_DAY4.md](PLAN_DAY4.md). Next: [PLAN_DAY6.md](PLAN_DAY6.md). Charter: [README.md](README.md).

**Status:** done.

---

## Graph

```
… → resolution → draft → hitl → interrupt (AWAITING_HUMAN)
approve resume → send → END
escalate → ESCALATED → END (no send)
```

`Send` is **not** on the inbound spine. Same as assistant: first run stops at HITL; approve calls send.

LangGraph options (pick one and document in `app/graph/app.py`):

1. `interrupt()` after hitl + Postgres checkpointer; `Command(resume=...)` on approve; **or**
2. Graph ends at hitl; `HitlService.approve` builds state and runs `make_send_node(deps)` (assistant pattern).

Operator spec must match: always park at HITL; never auto-send; `POST /tickets/{id}/approve` and `/escalate`.

---

## Resolution (parity ladder — no retry)

File: `app/graph/nodes/resolution.py`  
Reference: `p2p-ai-assistant/app/workflow/nodes/resolution.py`  
Util: `normalize_reference` (copy the function, not the Launchpad node class).

- [x] Load SAP approval + posted via `SAPPort`
- [x] Match: **exact ref** → **fuzzy ≥ 0.85** → **amount ± `MATCH_VALUE_TOLERANCE_*` + supplier**
- [x] Both sources / ambiguous / TOO_MANY → `requires_hitl`
- [x] VAT discrepancy vs extracted amount: LLM **notes only** (`VATReasoningOutput`), `VAT_DISCREPANCY`, HITL
- [x] PAID without clearing → HITL
- [x] Set `is_overdue` / `is_near_due` from `NEAR_DUE_DAYS` for Draft
- [x] Audit `RESOLVE` with `match_result`, `match_method`, `invoice_ref`

**Do not** widen tolerances and re-run the ladder this day.

Tests: port assistant `test_node_resolution.py` cases (memory SAP + tickets).

---

## Draft — deterministic target, LLM text

File: `app/graph/nodes/draft.py`  
Reference: `DraftNode._pick_target`

| Situation | Target |
|---|---|
| MULTIPLE / TOO_MANY / VAT | no draft → HITL |
| NOT_FOUND | `INVOICING` |
| IN_APPROVAL + overdue/near-due + owner | `APPROVAL_OWNERS` |
| IN_APPROVAL + overdue, no owner | HITL |
| IN_APPROVAL on-time | `SENDER` |
| POSTED BLOCKED or overdue PENDING | `PAYMENTS` |
| POSTED PENDING on-time / PARTIAL | `SENDER` |
| POSTED PAID + clearing | `SENDER` + `attach_payment_proof` |
| POSTED PAID no clearing | HITL |

- [x] LLM only writes `generated_text` (`DraftOutput`)
- [x] Persist `ResponseDraft` via `DraftPort`
- [x] Prompts: reuse assistant `app/llm/prompts.py` (copy into `app/llm/` in this repo)

---

## HITL + Send

- [x] Hitl: set `AWAITING_HUMAN`, save ticket, `should_stop` / interrupt; audit `HITL`
- [x] v1 **never** auto-sends (`CONFIDENCE_THRESHOLD` unused for send)
- [x] Send (after approve): mock resolve unless `NYLAS_SEND_ENABLED`; record `HumanReview`; ticket `RESOLVED`; audit `SEND` / `APPROVE` / `APPROVE_EDIT`
- [x] Escalate: `ESCALATED`, review `ESCALATED_TO_EMAIL`, no send

---

## FastAPI (assistant routes, no Streamlit)

Finish Day 2 runtime if still open, then:

- [x] `GET /health`
- [x] `POST /webhook/mock` → `process_email.delay`; sync fallback if Redis down (assistant `main.py`)
- [x] `GET /tickets`, `GET /tickets/{id}` (ticket + sender + draft + invoice + audit summaries)
- [x] `GET /tickets/{id}/draft`
- [x] `POST /tickets/{id}/approve` body `{ operator_id, final_text? }`
- [x] `POST /tickets/{id}/escalate` body `{ operator_id }`
- [x] `GET /stats` (counts by status) — assistant has it; include for parity
- [x] 404 ticket missing; **409** if not `AWAITING_HUMAN` or no draft

No `app/dashboard/`. CORS like assistant is fine for a future UI; do not add Streamlit.

---

## Definition of Done — Day 5

- [x] Inbound graph: … → resolution → draft → hitl
- [x] Approve/escalate work via HTTP without Streamlit
- [x] Draft table matches assistant
- [x] Resolution tests pass **without** Day 7 retry
- [x] Celery worker still runs the **inbound** graph only

---

## Out of scope

Eval suite (Day 6). Fuzzy-tolerance retry (Day 7). GIF/README visuals (Day 7). Streamlit.
