# Day 8 — Real LLM adapter + draft judge (~2h, +1h optional live eval)

> First post-lab day. Replace the pinned mock in the **worker** with a real structured-output LLM, behind the existing `LLMPort`. The graph, the nodes, and the eval routing do **not** change.
>
> Previous: [PLAN_DAY7.md](PLAN_DAY7.md). Next: [PLAN_DAY9.md](PLAN_DAY9.md). Charter: [README.md](README.md).

**Status:** done. The checklist below is the original brief and was not re-ticked. The adapter, the invoice facts in the draft prompt, and the token judge are in the repo.

Why this day exists: on the live webhook, `MockLLMAdapter` returns the same three answers for every email (`is_ap: true`, `INV-2026-0001` / 1250, a canned draft). Subject and body never change the path. After Day 8, the email text drives triage, intent, and the draft — so cases like paid-without-clearing (`INV-2026-PAID-NC`) work on the webhook, not only in eval.

---

## Block (~2h)

### 8.0 Setup (10 min)

- [ ] Add `openai` to `dependencies` in `pyproject.toml` (keep the list otherwise unchanged):

```toml
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "sqlmodel",
  "alembic",
  "psycopg2-binary",
  "celery[redis]",
  "pydantic-settings",
  "langgraph",
  "openai>=1.99",
]
```

- [ ] `pip install -e ".[dev]"`
- [ ] Confirm the settings already exist in `settings.py` (they do — do not rename them): `LLM_PRIMARY_MODEL`, `LLM_PRIMARY_API_KEY`, `LLM_PRIMARY_BASE_URL`, `LLM_FALLBACK_MODEL`, `LLM_FALLBACK_API_KEY`, `LLM_FALLBACK_BASE_URL`, `LLM_TIMEOUT_S`, `LLM_RETRY_BACKOFF_S`
- [ ] In `.env` (gitignored, never `.env.dev`): `LLM_PRIMARY_API_KEY=sk-...`
- [ ] Keep `.env.dev` **without** a key — a fresh clone must still run on the mock

### 8.1 Adapter — `app/adapters/openai_llm.py` (45 min)

Implements `LLMPort.generate(system_prompt, user_prompt, output_schema)` with OpenAI structured outputs. The node passes a Pydantic class; the adapter returns a validated instance of that class.

- [ ] Class `OpenAILLMAdapter(LLMPort)`:

```python
class OpenAILLMAdapter(LLMPort):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout_s: int = 15,
        retry_backoff_s: int = 2,
        fallback: "OpenAILLMAdapter | None" = None,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s)
        self._model = model
        self._retry_backoff_s = retry_backoff_s
        self._fallback = fallback
        self.calls: list[dict] = []

    async def generate(self, *, system_prompt, user_prompt, output_schema):
        completion = await self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=output_schema,
        )
        message = completion.choices[0].message
        if message.refusal:
            raise LLMRefusalError(message.refusal)
        if message.parsed is None:
            raise LLMOutputError(f"no parsed output for {output_schema.__name__}")
        return message.parsed
```

- [ ] Retry policy (keep it boring): on `openai.APITimeoutError`, `openai.APIConnectionError`, `openai.RateLimitError` → `await asyncio.sleep(retry_backoff_s)` → one more try → then `fallback.generate(...)` if configured → else re-raise. Do **not** retry on `BadRequestError` (schema problem; retrying hides it).
- [ ] Record each call in `self.calls` with `schema`, `model`, and `completion.usage` (prompt/completion tokens). Not used yet; it is where cost telemetry will come from later.
- [ ] Define `LLMRefusalError` and `LLMOutputError` in the same file (or `app/adapters/errors.py`).
- [ ] Create the `AsyncOpenAI` client **per adapter instance**, never at module level. The worker calls `asyncio.run(...)` once per task; a module-level async client gets bound to a closed event loop on the second task.

Structured-output schema check — every schema the nodes send must be accepted in strict mode:

| Schema | File | Watch out for |
|---|---|---|
| `TriageOutput` | `app/domain/schemas.py` | none |
| `IntentOutput` | `app/graph/nodes/intent.py` | `Intent` enum (fine); optional fields `language`, `extracted_ref`, `extracted_amount` with `= None` defaults |
| `VATReasoningOutput` | `app/graph/nodes/resolution.py` | none |
| `DraftOutput` | `app/graph/nodes/draft.py` | none |

- [ ] If the SDK rejects the `= None` defaults on `IntentOutput`, keep the fields as `str | None` / `float | None` **without** defaults (strict mode makes every field required but nullable). Do not change field names — the eval and the node read them.

### 8.2 Wiring — `app/api/deps.py` (15 min)

The switch goes in `build_workflow_deps`, **not** in `app/domain/deps.py`. `WorkflowDeps` is a plain domain dataclass; it must not import `openai` or any adapter (hexagon rule: domain does not know adapters).

- [ ] Add a factory next to the existing mock defaults:

```python
def _default_llm() -> LLMPort:
    if settings.LLM_PRIMARY_API_KEY:
        fallback = None
        if settings.LLM_FALLBACK_MODEL and settings.LLM_FALLBACK_API_KEY:
            fallback = OpenAILLMAdapter(
                api_key=settings.LLM_FALLBACK_API_KEY,
                model=settings.LLM_FALLBACK_MODEL,
                base_url=settings.LLM_FALLBACK_BASE_URL,
                timeout_s=settings.LLM_TIMEOUT_S,
                retry_backoff_s=settings.LLM_RETRY_BACKOFF_S,
            )
        return OpenAILLMAdapter(
            api_key=settings.LLM_PRIMARY_API_KEY,
            model=settings.LLM_PRIMARY_MODEL,
            base_url=settings.LLM_PRIMARY_BASE_URL,
            timeout_s=settings.LLM_TIMEOUT_S,
            retry_backoff_s=settings.LLM_RETRY_BACKOFF_S,
            fallback=fallback,
        )
    return MockLLMAdapter(responses=[_DEFAULT_TRIAGE, _DEFAULT_INTENT, _DEFAULT_DRAFT])
```

- [ ] `build_workflow_deps(session, *, llm=None)` → `llm=llm or _default_llm()`
- [ ] The explicit `llm=` argument still wins. That keeps tests and eval off the network.
- [ ] Verify no test builds deps without `llm=` **and** reaches an LLM node:
  - `tests/test_process_email.py` — passes `llm=` ✔
  - `tests/test_day4.py` — passes `llm=` ✔
  - `tests/test_api.py::test_ingest_falls_back_sync_when_redis_down` — no `llm=`, but `evil.example` stops at security before any LLM call ✔
- [ ] `GET /tickets/{id}`, approve, and escalate also call `build_workflow_deps`. They never call the LLM, so a real adapter there costs nothing. Leave it.

### 8.3 Give the draft node the facts (25 min)

Today `draft.py` sends only `Subject + body` to the LLM. The mock ignores the prompt, so nobody noticed. A real model has no invoice data and the system prompt forbids inventing numbers — it would write empty filler.

- [ ] Add `build_draft_user_prompt(...)` in `app/llm/prompts.py`:

```python
def build_draft_user_prompt(*, ticket, invoice, target, to_email, match_result, intent) -> str:
    lines = [
        f"Intent: {intent or 'unknown'}",
        f"Reply to: {to_email} ({target.value})",
        f"Match result: {match_result.value}",
    ]
    if invoice is not None:
        lines += [
            f"Invoice ref: {invoice.invoice_ref}",
            f"Amount: {invoice.amount} {invoice.currency}",
            f"Stage: {invoice.stage.value}",
            f"Status: {invoice.status.value if invoice.status else 'unknown'}",
            f"Due date: {invoice.due_date or 'unknown'}",
            f"Clearing document: {'yes' if invoice.clearing_document else 'no'}",
            f"Payment date: {invoice.payment_date or 'unknown'}",
            f"Blocking reason: {invoice.payment_blocking_reason or 'none'}",
        ]
    lines += ["", f"Original subject: {ticket.subject}", "", ticket.body]
    return "\n".join(lines)
```

- [ ] In `make_draft_node`, call it with the values the node already has (`ticket`, `invoice`, `target`, `_to_email(...)`, `match_result`, `ticket.intent`) and pass the result as `user_prompt`.
- [ ] Add one rule to `DRAFT_SYSTEM_PROMPT`: "Only state that an invoice is paid when Clearing document is yes." (Paid-without-clearing already gets no draft from `pick_target`; this is defence in depth.)
- [ ] Unit test `tests/test_draft_prompt.py`: prompt contains the invoice ref, the amount, `Clearing document: no` when absent, and the original body.
- [ ] `MockLLMAdapter` and `FixtureGuidedLLM` ignore `user_prompt` → eval and existing tests are unaffected.

### 8.4 Draft judge — `required_tokens` / `forbidden_tokens` (30 min)

`app/llm/judge.py` compares draft text by exact string. That only passes when the "model" echoes the fixture, which a real model never does.

- [ ] New fixture field, inside `expected`, only on fixtures that produce a draft:

```json
"draft_checks": {
  "required_tokens": ["INV-2026-0001"],
  "forbidden_tokens": ["has been paid", "was paid"]
}
```

- [ ] New signature in `app/llm/judge.py`:

```python
def judge_draft(checks: dict | None, actual_text: str | None, *, expect_draft: bool) -> bool:
    if not expect_draft:
        return actual_text is None
    if not actual_text:
        return False
    text = actual_text.lower()
    checks = checks or {}
    if any(tok.lower() not in text for tok in checks.get("required_tokens", [])):
        return False
    if any(tok.lower() in text for tok in checks.get("forbidden_tokens", [])):
        return False
    return True
```

- [ ] Update the call in `scripts/eval_harness.py::run_fixture`:

```python
draft_ok = judge_draft(
    expected.get("draft_checks"),
    actual.get("generated_text"),
    expect_draft=expected.get("draft_target") is not None,
)
```

- [ ] Fill `draft_checks` for the **11** fixtures that have `generated_text` today: 001, 002, 003, 009, 010, 011, 012, 013, 014, 016, 018. Rules:
  - `required_tokens`: the fixture's `extracted_ref` when it is not null
  - `forbidden_tokens`: claims that contradict SAP for that case

| Fixture | Case | required | forbidden (examples) |
|---|---|---|---|
| 002 | in approval, on time | `INV-2026-0001` | `has been paid`, `was paid` |
| 003 | posted, paid + clearing | `INV-2026-0002` | `not yet paid`, `pending` |
| 009 | posted, blocked | `INV-2026-BLOCKED` | `has been paid` |
| 018 | posted, partial | `INV-2026-PARTIAL` | `fully paid` |
| others | — | their `extracted_ref` | `has been paid` unless status is paid with clearing |

- [ ] Change the canned `generated_text` in those fixtures so it contains the ref (e.g. `"Thank you. We are reviewing invoice INV-2026-0001."`). `FixtureGuidedLLM` returns it verbatim, so the **offline** judge passes too.
- [ ] Make the change in `scripts/write_email_fixtures.py` first, then regenerate the JSON — otherwise the next regeneration wipes it. `git diff fixtures/emails/` must only show `generated_text` + `draft_checks`.
- [ ] Document `draft_checks` in `fixtures/emails/README.md` (one paragraph).
- [ ] `scripts/run_eval.py`: print a `draft_judge: FAIL` line under any row where `draft_judge` is false. Do **not** add it to `workflow_ok` — workflow success stays comparable to Days 6–7.
- [ ] Tests `tests/test_judge.py`: required missing → False; forbidden present → False; case-insensitive; no draft expected and none produced → True; draft expected and none produced → False; draft produced when none expected → False.

### Gate

```powershell
pytest
python scripts/run_eval.py
```

- Eval workflow success unchanged (was 1.00); no `draft_judge: FAIL` lines
- With the key in `.env`, API + Celery running:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/webhook/mock -ContentType "application/json" -Body '{"thread_id":"d8-paidnc","message_id":"msg-d8-paidnc-1","from":"billing@acme-supplies.com","subject":"INV-2026-PAID-NC","body":"INV-2026-PAID-NC 150 EUR shows paid. Can you confirm?"}'
Invoke-RestMethod -Method POST -Uri http://localhost:8000/webhook/mock -ContentType "application/json" -Body '{"thread_id":"d8-paid","message_id":"msg-d8-paid-1","from":"billing@acme-supplies.com","subject":"Was INV-2026-0002 paid?","body":"Need proof for INV-2026-0002 / 980.50 EUR."}'
```

- `INV-2026-PAID-NC` → `awaiting_human`, **no** draft (the case that was eval-only on Day 6)
- `INV-2026-0002` → `awaiting_human`, draft to the sender, `attach_payment_proof: true`, text mentions the ref
- Without a key in `.env` → the same POSTs behave exactly as before (mock)

### Git

- Commit: `feat: OpenAI structured-output LLM adapter behind LLMPort`
- Commit: `feat: draft prompt carries invoice facts`
- Commit: `test: token-based draft judge`

---

## Optional (~1h) — live draft eval

Only after the gate passes. Costs ~11 draft calls per run.

- [ ] `HybridEvalLLM` in `scripts/eval_harness.py`: delegates `TriageOutput`, `IntentOutput`, `VATReasoningOutput` to `FixtureGuidedLLM` (routing stays deterministic) and `DraftOutput` to `OpenAILLMAdapter`
- [ ] Use it in `run_fixture` when `settings.EVAL_LIVE_LLM` is true **and** a key is set
- [ ] Run: `$env:EVAL_LIVE_LLM="true"; python scripts/run_eval.py`
- [ ] Write the result to `golden_dataset/baselines/live_v1.json`, not `v1.json`

---

## Definition of Done — Day 8

- [ ] Worker uses the real LLM when `LLM_PRIMARY_API_KEY` is set, mock otherwise
- [ ] No adapter import in `app/domain/`
- [ ] Draft prompt includes invoice facts
- [ ] Judge is token-based and tested; offline eval still 1.00
- [ ] Paid-without-clearing reproducible on the webhook

---

## Out of scope for this day

Anthropic/other providers, streaming, prompt caching, Langfuse/tracing, a cost dashboard (only record `usage` in `calls`), changing graph routing, changing `pick_target`.
