# Day 6 — Eval / shadow parity (not UI)

> Same golden dataset and success bar as the assistant, driven by **LangGraph `ainvoke`** instead of `TicketWorkflow.run`. No Streamlit.
>
> Reference: `p2p-ai-assistant/scripts/eval_harness.py`, `scripts/run_eval.py`, `scripts/run_shadow.py`, `app/llm/judge.py`, `fixtures/emails/001_*.json`–`020_*.json`, `tests/test_eval_suite.py`.
>
> Previous: [PLAN_DAY5.md](PLAN_DAY5.md). Next: [PLAN_DAY7.md](PLAN_DAY7.md). Charter: [README.md](README.md).

**Status:** done.

Day 6 measures **parity** with the original product. Do **not** enable the Day 7 resolution retry loop in the default eval graph (or gate it off with a setting defaulting to disabled).

---

## Fixtures

- [x] Emails 001–020 from assistant `fixtures/emails/` (copied on Day 3)
- [x] SAP + senders fixtures used by `MockSAPAdapter` / `MockSenderDirectory`
- [x] Same `input` + `expected` schema as assistant golden files

Lab emails live in `fixtures/emails/`. Thread continuations are **new tickets** (unique `message_id`). Extra SAP rows (overdue, blocked, INV-MULTI, …) are additive; INV-2026-0001 / 0002 stay unique exact matches.

---

## Harness

- [x] `scripts/eval_harness.py`: `FixtureGuidedLLM` (or equivalent) implements `LLMPort` from fixture expected outputs
- [x] `run_fixture` calls `build_graph(deps).ainvoke({ "raw_payload": ... })` (async) — **not** `TicketWorkflow`
- [x] In-memory stores for tickets/audit/drafts unless a dedicated eval DB is documented
- [x] Dimensions (same as assistant `run_eval.py`): `intent`, `ticket_status`, `invoice_resolution`, `draft_target`, `to_email`, `attach_payment_proof`, `human_action_needed`
- [x] Optional `judge_draft` if assistant eval uses it for text quality

---

## Runner

- [x] `scripts/run_eval.py` writes `golden_dataset/baselines/v1.json` (or lab-equivalent path)
- [x] Exit code **1** if workflow success &lt; **0.80** (`WORKFLOW_SUCCESS_THRESHOLD`)
- [x] Optional `scripts/run_shadow.py` → `shadow_v1.json` (assistant Fase 7 simulated shadow)

Document: thread continuations in the assistant harness often run as **new** tickets; match that unless you explicitly add thread eval.

---

## Tests

- [x] `tests/test_eval_suite.py` smoke: load fixtures, run 1–2 cases, harness does not import Streamlit or Launchpad `core/`

---

## Definition of Done — Day 6

- [x] `python scripts/run_eval.py` comparable to assistant (same dimensions, 0.80 bar)
- [x] Graph under test is LangGraph, inbound through HITL (no auto-send)
- [x] Resolution retry **off** so scores are comparable to assistant
- [x] No dashboard

---

## Out of scope

OCR, live LLM required for CI (`EVAL_LIVE_LLM` optional like assistant). Day 7 visuals and retry loop.
