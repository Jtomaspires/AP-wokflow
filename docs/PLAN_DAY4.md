# Day 4 — Spine through Routing (Thread → Intent → Sender → Routing)

> Grow `StateGraph` from three nodes to the assistant spine **up to Routing**. Security gains SPF/DKIM parity. Per-node audit like `Workflow._record_audit`.
>
> Reference: `p2p-ai-assistant/app/workflow/nodes/{security,thread,triage,intent,sender,routing}.py`, `tests/test_nodes_0_to_5.py`, `tests/test_workflow_integration.py`.
>
> Previous: [PLAN_DAY3.md](PLAN_DAY3.md). Next: [PLAN_DAY5.md](PLAN_DAY5.md). Charter: [README.md](README.md).

**Status:** closed — spine through routing + SPF/DKIM + per-node audit. Resolution is a no-op stub. Next: [PLAN_DAY5.md](PLAN_DAY5.md).

Nodes = `make_*_node(deps) -> (state) -> dict`. Routers = `add_conditional_edges`. Do not copy `BaseRouter`.

---

## Graph after this day

```
START → ingest → security → thread ─┬─ continuation → (resolution stub / END until Day 5)
                                    └─ new → triage ─┬─ discard → END
                                                     └─ intent ─┬─ skip_identity → (resolution stub / END)
                                                                └─ sender → routing ─┬─ DELEGATE → END
                                                                                     └─ MINE → (resolution stub / END)
```

Until Day 5, “resolution stub” may be **END** with ticket still `OPEN` and state flags set — document it. Prefer leaving a `resolution` node placeholder that no-ops so Day 5 only fills the body.

---

## State

Extend `LabState` / graph state toward `ProcessingContext` (assistant `app/domain/context.py`):

- Keep: `raw_payload`, `ticket_id`, `should_stop`, `stop_reason`
- Add as needed: `event` (or persist only), `route` (`triage` | `resolution` | `end`), `skip_identity`, `is_thread_continuation`, `extracted_ref`, `extracted_amount`, `intent`, `sender_id`
- **Never** store `WorkflowDeps` in state

---

## Security — assistant parity

File: `app/graph/nodes/security.py`  
Reference: `p2p-ai-assistant/app/workflow/nodes/security.py`

- [x] `SECURITY_CHECK_ENABLED=False` → pass
- [x] Domain not in `SENDER_DOMAIN_WHITELIST` → `QUARANTINED`, stop
- [x] If `SPF_DKIM_ENABLED`: both SPF and DKIM fail → `QUARANTINED`; partial fail → confidence penalty (−0.2), continue
- [x] Audit `QUARANTINE` / `PASS`

Tests: whitelist, flag off, dual fail, partial fail (do not quarantine).

---

## Thread

File: `app/graph/nodes/thread.py`  
Reference: `thread.py`

- [x] `list_by_thread_id` (Day 3 port)
- [x] OPEN or AWAITING_HUMAN on same thread → continuation → route **resolution**, set `is_thread_continuation`
- [x] RESOLVED → reopen → resolution
- [x] ESCALATED → update body, **stop**
- [x] Else → route **triage** (new thread)

Tests: new vs continuation vs escalated stop.

---

## Triage — no longer always END

File: `app/graph/nodes/triage.py`

- [x] Same discard rule: `not is_ap` and conf ≥ `TRIAGE_DISCARD_MIN_CONFIDENCE` → `DISCARDED`, END
- [x] Else → **intent** (not END)
- [x] Audit `DISCARD` / `PASS`

---

## Intent

File: `app/graph/nodes/intent.py`  
Reference: `intent.py`, `IntentOutput`, prompts

- [x] LLM → `payment_status` | `delay_reason` | `future_timing` | `unknown` + extract ref/amount/language
- [x] Persist intent/language on ticket
- [x] `UNKNOWN` **or** confidence &lt; `INTENT_MIN_CONFIDENCE` → `skip_identity=True` → skip sender/routing → resolution
- [x] Else → sender

Tests: known intent vs unknown vs low confidence.

---

## Sender + Routing

Files: `sender.py`, `routing.py` equivalents under `app/graph/nodes/`

- [x] Sender: email match 0.9 → unique domain 0.6 → unknown 0.0; **never** stops
- [x] Routing: if rule operator ≠ `DEFAULT_OPERATOR_ID` → `DELEGATED`, stop; else MINE → resolution
- [x] Audit `IDENTIFY`, `MINE`, `DELEGATE`

---

## Compile (`app/graph/app.py`)

- [x] Nodes: ingest, security, thread, triage, intent, sender, routing, resolution stub
- [x] Conditional edges for all routers above
- [x] Audit wrapper after each node (`deps.audit.append`)

Integration tests (memory deps, `ainvoke`):

- [x] Paths up to routing (memory `ainvoke`)
- [x] Discard never calls intent LLM
- [x] Delegate never calls the resolution stub

---

## Definition of Done — Day 4

- [x] Graph topology matches assistant through Routing (resolution is a stub)
- [x] SPF/DKIM behaviour matches assistant
- [x] Audit rows per node in Postgres tests
- [x] No Draft/HITL/Send, no Streamlit, no resolution retry loop

---

## Out of scope

Resolution matching, draft table, HITL interrupt, Send, eval, Day 7 retry.
