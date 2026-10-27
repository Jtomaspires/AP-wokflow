# Day 12 — Fixes and tests (~4h)

> Six problems found by reading the code. Each section: what is wrong, what to change, and the tests to write.
>
> Oct 12, 2026. @ko
>
> Previous: [PLAN_DAY11.md](PLAN_DAY11.md). Charter: [README.md](README.md).

**Status:** Fix 1 through Fix 6 done.

Do one fix at a time. Give the Cursor the "What to change" block for that fix plus the current file. Do not ask for all six in one pass — the context mixes and the tests come out wrong.

Recommended order is impact first. The two Alembic changes are last, so the earlier fixes can be tested without a migration.

| Order | Fix | Main files | Alembic? | Estimate |
| --- | --- | --- | --- | --- |
| 1 | Fix 2: SPF/DKIM actually affects a decision | `security.py`, `intent.py`, `state.py` | No | 30 min |
| 2 | Fix 4: `extraction_confidence` | `intent.py`, `resolution.py` | No | 45 min |
| 3 | Fix 3: truncate thread body | `thread.py`, `settings.py` | No | 30 min |
| 4 | Fix 5: no routing rule can park for a human | `routing.py`, `settings.py` | No | 30 min |
| 5 | Fix 6: HITL deadline | `hitl.py`, `models.py`, `main.py`, `settings.py` | Yes | 60 min |
| 6 | Fix 1: ingest content hash | `ingest.py`, `postgres_tickets.py` | Yes | 60 min |

Fixes 2, 4, 3, and 5 need no migration and can be tested without restarting the database. Fixes 6 and 1 need `alembic revision --autogenerate` and `alembic upgrade head`.

---

## Fix 1 — Ingest: duplicate by content hash

**Done.** The hash is stored on the ticket and checked after `message_id`.

**Problem:** The duplicate check uses only `message_id`. A manual resend with a mutated header creates a new ticket.

**What to change in `app/graph/nodes/ingest.py`:**

```python
import hashlib

def _content_hash(event) -> str:
    raw = f"{event.from_email}|{event.subject}|{(event.body or '')[:300]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

After the `message_id` check, add:

```python
content_hash = _content_hash(event)
existing_hash = deps.tickets.get_by_content_hash(content_hash)
if existing_hash is not None:
    return {
        "should_stop": True,
        "ticket_id": str(existing_hash.id),
        "stop_reason": "duplicate",
        "audit_action": AuditAction.INGEST.value,
        "audit_metadata": {"reason": "content_duplicate"},
        **auth,
    }
```

Add a `content_hash VARCHAR(16)` column on `tickets` (Alembic) and `get_by_content_hash` on `TicketRepo`.

**Tests in `tests/test_node_ingest.py`:**

- [x] `test_resubmit_different_message_id_same_content_is_duplicate` — same from + subject + body, different `message_id`. Expect `should_stop=True`, `stop_reason='duplicate'`, `audit_metadata['reason']='content_duplicate'`.
- [x] `test_same_content_hash_different_sender_is_new` — different from, same subject and body. Expect `should_stop=False` (the hash includes `from_email`).

---

## Fix 2 — Security: SPF/DKIM penalty has no effect

**Done.** A partial SPF/DKIM failure sets `spf_dkim_penalty` on graph state. Intent subtracts it before `skip_identity`.

**Problem:** The −0.2 penalty is applied to `ticket.confidence`, but triage and intent use the LLM `output.confidence` and overwrite that value. The penalty affects no decision.

**What to change:**

Store the penalty on graph state and apply it to the intent confidence.

```python
# security.py — pass it in state instead of mutating ticket.confidence:
return {
    "should_stop": False,
    "spf_dkim_penalty": 0.2,  # new state field
    "audit_action": AuditAction.PASS.value,
    "audit_metadata": {"reason": "spf_dkim_partial", "penalty": 0.2},
}
```

```python
# intent.py — adjust confidence with the penalty:
penalty = state.get("spf_dkim_penalty") or 0.0
adjusted_confidence = max(0.0, output.confidence - penalty)
skip = output.intent is Intent.UNKNOWN or adjusted_confidence < deps.settings.INTENT_MIN_CONFIDENCE
```

Add `spf_dkim_penalty: float` to `LabState`.

**Tests in `tests/test_node_security.py`:**

- [x] `test_spf_dkim_partial_fail_reduces_intent_confidence` — SPF fails, DKIM passes. Expect state `spf_dkim_penalty=0.2`. Intent confidence `0.75` becomes `0.55` (above the `0.5` threshold).
- [x] `test_spf_dkim_partial_fail_can_flip_skip_identity` — intent confidence `0.65` minus `0.2` is `0.45`, so `skip_identity=True`. Expect the graph to skip sender and routing and go straight to resolution.

---

## Fix 3 — Thread: unbounded body passed to the LLM

**Done.** Continuations and escalated threads keep the last `THREAD_MAX_HISTORY_CHARS` of the body. One prefix is used, including when the window has no separator.

**Problem:** On a continuation, bodies are concatenated with no limit. On a long thread the LLM receives a huge block, the newest message sits at the end, and models lose attention there.

**What to change in `app/graph/nodes/thread.py`:**

```python
def _truncate_history(body: str, max_chars: int) -> str:
    if len(body) <= max_chars:
        return body
    tail = body[-max_chars:]
    sep = "\n\n---\n\n"
    idx = tail.find(sep)
    if idx != -1:
        tail = tail[idx + len(sep):]
    return "[...earlier messages truncated...]\n\n---\n\n" + tail
```

Apply before both saves:

```python
prior.body = _truncate_history(
    f"{prior.body}\n\n---\n\n{ticket.body}",
    deps.settings.THREAD_MAX_HISTORY_CHARS,
)
```

The escalated path uses the same call. Add `THREAD_MAX_HISTORY_CHARS: int = 2000` to `settings.py`.

**Tests in `tests/test_node_thread.py`:**

- [x] `test_truncate_history_leaves_short_body_unchanged` — body under 2000 characters. Result equals the input and has no truncation prefix.
- [x] `test_truncate_history_keeps_last_chars_without_separator` — long body, no separator. Result starts with the prefix, and the text after it is `body[-2000:]`.
- [x] `test_truncate_history_starts_after_separator_in_window` — long body whose last 2000 characters contain `\n\n---\n\n`. Kept text is what follows that first separator.

---

## Fix 4 — Intent: missing `extraction_confidence`

**Done.** Below `0.5`, resolution drops the extracted ref and amount. A missing score stays `1.0`.

**Problem:** The LLM extracts `extracted_ref` and `extracted_amount` but returns no confidence on that extraction. A bad extract (partial ref, amount that includes VAT) is what resolution matches on, so a real SAP invoice can miss silently.

**What to change in `app/graph/nodes/intent.py`:**

```python
class IntentOutput(BaseModel):
    intent: Intent
    confidence: float
    language: str | None = None
    extracted_ref: str | None = None
    extracted_amount: float | None = None
    extraction_confidence: float = 1.0  # new field
```

Add to the system prompt:

```
Set extraction_confidence between 0 and 1:
1.0 = exact match (e.g. 'INV-2026-0001')
0.7 = partial or likely match
0.3 = inferred or ambiguous
0.0 = could not extract
```

Return it on the node state:

```python
"extraction_confidence": output.extraction_confidence,
```

In `app/graph/nodes/resolution.py`:

```python
if state.get("extraction_confidence", 1.0) < 0.5:
    extracted_ref = None
    extracted_amount = None
```

`0.0` is weak. A missing key stays `1.0`, so existing callers keep the ref. Supplier hint alone does not match, so a weak extraction ends as `not_found`.

**Tests in `tests/test_node_resolution.py` and `tests/test_day4.py`:**

- [x] `test_low_extraction_confidence_ignores_ref` — `extraction_confidence=0.3`, ref `INV-2026-0001`. Result is `not_found` and `invoice_ref` is null.
- [x] `test_high_extraction_confidence_uses_ref` — `extraction_confidence=0.8`, same ref. Result is an exact match.
- [x] `test_low_extraction_confidence_resolution_ignores_ref` — graph run, intent confidence `0.9` and extraction confidence `0.3`. Resolution does not use the ref.

---

## Fix 5 — Routing: no rule should be able to wait for a human

**Done.** A missing rule assigns `DEFAULT_OPERATOR_ID` or leaves `assigned_operator_id` empty, depending on `ROUTING_NO_RULE_BEHAVIOUR`. A matching rule is unchanged. The HITL node still parks the ticket later.

**Problem:** When the sender has no routing rule, the system falls back to `DEFAULT_OPERATOR_ID` (`op_joao`). With several operators, an email with no rule is assigned to the wrong person. A case with no rule should be assignable by a human.

**What to change in `app/graph/nodes/routing.py`:**

```python
# settings.py
DEFAULT_OPERATOR_ID: str = "op_joao"
ROUTING_NO_RULE_BEHAVIOUR: str = "default"  # "default" | "hitl"
```

Handle a missing rule before `operator_id != default_op`. Otherwise an empty operator looks like a delegate and the graph stops.

```python
if rule is None and deps.settings.ROUTING_NO_RULE_BEHAVIOUR == "hitl":
    ticket.assigned_operator_id = None
    # continue to resolution; hitl node parks the ticket
    return {
        "should_stop": False,
        "routing_outcome": "no_rule_hitl",
        "audit_metadata": {"reason": "no_rule_hitl", "operator_id": None},
    }
# "default": assigned_operator_id = DEFAULT_OPERATOR_ID, routing_outcome = "no_rule_default"
```

**Tests in `tests/test_node_routing.py`:**

- [x] `test_no_rule_default_assigns_op_joao` — no rule, behaviour `default`. `assigned_operator_id` is `op_joao`, outcome `no_rule_default`.
- [x] `test_no_rule_hitl_leaves_operator_unset` — no rule, behaviour `hitl`. `assigned_operator_id` is null, outcome `no_rule_hitl`, graph continues.
- [x] `test_existing_rule_ignores_no_rule_setting` — a rule for `op_other`, with either setting. Status is `DELEGATED` and `routing_outcome` is absent.

---

## Fix 6 — HITL: no deadline and no late alert

**Done.** A ticket that reaches HITL stores `hitl_deadline`. A due date becomes 00:00 UTC that day. Otherwise the deadline is now plus 24 hours. `GET /stats` adds `hitl_overdue`. The All tile does not add that count on top of the status totals.

**Problem:** A ticket can sit in `awaiting_human` forever. There is no timeout and no alert. Overdue invoices stay there until someone approves.

**What to change:**

**1. Add `hitl_deadline` to the ticket model:**

```python
# app/domain/models.py
hitl_deadline: datetime | None = None
```

**2. Set the deadline in the HITL node. `due_date` is a date, so it is stored as a timestamp at 00:00 UTC:**

```python
due = Invoice.model_validate(invoice_dump).due_date
deadline = datetime(due.year, due.month, due.day, tzinfo=UTC)
# no due date:
deadline = datetime.now(UTC) + timedelta(hours=deps.settings.HITL_DEFAULT_DEADLINE_H)
```

**3. `/stats` reports overdue HITL tickets:**

```python
counts = TicketRepo(session).count_by_status()
counts["hitl_overdue"] = TicketRepo(session).count_hitl_overdue()
```

Only `awaiting_human` tickets with a deadline before now count. A naive timestamp is treated as UTC.

**4. Add `HITL_DEFAULT_DEADLINE_H: int = 24` to `settings.py`.**

**Tests in `tests/test_hitl.py`:**

- [x] `test_hitl_sets_deadline_from_invoice_due_date` — due date `2026-01-01`. Deadline is `2026-01-01 00:00 UTC`.
- [x] `test_hitl_sets_default_deadline_when_no_invoice` — no `invoice_dump`. Deadline is about now + 24h.
- [x] `test_count_hitl_overdue_returns_correct_count` — one overdue awaiting ticket, one future awaiting ticket, and one resolved ticket with a past deadline. Count is 1.
