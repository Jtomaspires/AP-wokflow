# Email mock fixtures — inventory and expected outcomes

Source: `fixtures/emails/` (30 JSON files). Outcomes below are what each fixture’s `expected` block scores in the golden eval, not only what the subject line suggests.

Each eval run opens a **fresh store** per fixture. `depends_on` is not chained, so **022** and **027** do not prove cross-fixture behaviour in `scripts/run_eval.py` (coverage lives in unit tests).

Regenerate via `scripts/write_email_fixtures.py` rather than hand-editing JSON when possible. See also `fixtures/emails/README.md`.

---

## Full inventory

| # | Name | From | Subject / body (summary) | Expected outcome |
|---|---|---|---|---|
| **001** | invoice_not_found | billing@acme-supplies.com | `INV-NOPE` / 10 EUR | `awaiting_human` · SAP **not_found** · draft **invoicing** → `invoicing@company.com` |
| **002** | in_approval_on_time | billing@acme-supplies.com | `INV-2026-0001` / 1250 | `awaiting_human` · **match** · draft **sender** (in approval, on time) |
| **003** | posted_paid_clearing | billing@acme-supplies.com | `INV-2026-0002` paid + proof | `awaiting_human` · **match** · draft **sender** + **payment proof** |
| **004** | unknown_domain_quarantine | phish@evil.example | Invoice / Pay now | **quarantined** (whitelist) · no draft |
| **005** | not_ap_discard | billing@acme-supplies.com | Team lunch / dessert? | **discarded** (not AP) · no draft |
| **006** | delegate_other_operator | other@vendor.com | `INV-2026-0001` | **delegated** (routing) · stops before SAP |
| **007** | vat_discrepancy | billing@acme-supplies.com | `INV-2026-0001` billed 1537.50 incl. VAT | `awaiting_human` · **vat_discrepancy** · **no draft** |
| **008** | multiple_sources | billing@acme-supplies.com | `INV-MULTI` / 100 EUR | `awaiting_human` · **multiple** · **no draft** |
| **009** | posted_blocked | billing@acme-supplies.com | `INV-2026-BLOCKED` / 220 | `awaiting_human` · **match** · draft **payments** → `payments@company.com` |
| **010** | in_approval_overdue_owner | billing@acme-supplies.com | `INV-2026-OVERDUE` / 500 late | `awaiting_human` · **match** · draft **approval_owners** → `ap-owner@company.com` |
| **011** | unknown_intent | billing@acme-supplies.com | Hello / Can you help? | `awaiting_human` · intent **unknown** · skip identity · **not_found** · draft **invoicing** |
| **012** | low_confidence_intent | billing@acme-supplies.com | Maybe an invoice? / Not sure… | `awaiting_human` · low intent conf · **not_found** · draft **invoicing** |
| **013** | delay_reason | billing@acme-supplies.com | Why delayed `INV-2026-0001` | `awaiting_human` · intent **delay_reason** · **match** · draft **sender** |
| **014** | future_timing | billing@acme-supplies.com | When will `INV-2026-0001` be paid? | `awaiting_human` · intent **future_timing** · **match** · draft **sender** |
| **015** | fuzzy_ref | billing@acme-supplies.com | `INV-2026-000l` (lowercase L) | `awaiting_human` · **multiple** (fuzzy) · **no draft** |
| **016** | amount_supplier_match | billing@acme-supplies.com | UNKNOWN-99 / 1250.50 ACME | `awaiting_human` · **match** by amount+supplier · draft **sender** |
| **017** | spf_dkim_fail | billing@acme-supplies.com | `INV-2026-0001` · SPF+DKIM false | **quarantined** · no draft |
| **018** | posted_partial | billing@acme-supplies.com | `INV-2026-PARTIAL` / 300 | `awaiting_human` · **match** · draft **sender** (no proof) |
| **019** | paid_no_clearing | billing@acme-supplies.com | `INV-2026-PAID-NC` / 150 “shows paid” | `awaiting_human` · **match** · **no draft** (clearing guardrail) |
| **020** | overdue_no_owner | billing@acme-supplies.com | `INV-2026-NOOWNER` / 400 overdue | `awaiting_human` · **match** · **no draft** (overdue, no owner) |
| **021** | spf_only_fail_penalty | billing@acme-supplies.com | Same as 002 · SPF false, DKIM true | `awaiting_human` · continues · **match** · draft **sender** (penalty 0.2) |
| **022** | content_duplicate_resubmit | billing@acme-supplies.com | Same text as 002 | Expected `stopped` / dedup — **eval fails on purpose** (fresh store per fixture) |
| **023** | low_extraction_confidence | billing@acme-supplies.com | Invoice last month ~1000€, no ref | `awaiting_human` · **not_found** · draft **invoicing** |
| **024** | multilingual_portuguese | billing@acme-supplies.com | PT: status `INV-2026-0001` 1250 | `awaiting_human` · **match** · draft **sender** |
| **025** | adversarial_prompt_injection | billing@acme-supplies.com | `INV-2026-0001` + IGNORE… attacker@… | `awaiting_human` · **match** · draft **sender** (code ignores injection) |
| **026** | overdue_invoice_in_approval | billing@acme-supplies.com | `INV-2026-OVERDUE` urgent (longer text) | Same as **010**: draft **approval_owners** |
| **027** | thread_continuation_context | billing@acme-supplies.com | “Any update…?” (thread of 002) | Expected **match** · draft **approval_owners** (near-due) — eval **does not** load 002 first |
| **028** | amount_mismatch_tolerance_edge | billing@acme-supplies.com | `INV-2026-0001` but 1275.00 | `awaiting_human` · **match** (tolerance) · draft **sender** |
| **029** | spam_like_ap_content | billing@acme-supplies.com | URGENT / FINAL NOTICE / fake IBAN | `awaiting_human` · **not_found** · draft **invoicing** (whitelist pass; spam ≠ quarantine) |
| **030** | subsidiary_domain_whitelisted | ap@group-subsidiary.com | `INV-2026-0002` 980.50 | `awaiting_human` · **match** · draft **sender** + proof (domain on whitelist) |

---

## Grouped by outcome type

### Early stop

| Outcome | Fixtures |
|---|---|
| Quarantine | 004, 017 |
| Discard | 005 |
| Delegate | 006 |

### No draft (HITL decides)

| Outcome | Fixtures |
|---|---|
| VAT / multiple / fuzzy | 007, 008, 015 |
| Paid without clearing | 019 |
| Overdue, no approval owner | 020 |

### Internal draft

| Target | Fixtures | To |
|---|---|---|
| Invoicing | 001, 011, 012, 023, 029 | `invoicing@company.com` |
| Payments | 009 | `payments@company.com` |
| Approval owner | 010, 026 (027 by design) | `ap-owner@company.com` |

### Supplier draft (`sender`)

| Fixtures | Notes |
|---|---|
| 002, 013, 014, 016, 018, 021, 024, 025, 028 | Reply to sender |
| 003, 030 | Reply to sender + `attach_payment_proof` |

### Special / weak in golden eval

| Fixture | Issue |
|---|---|
| 022 | Content-hash dedup needs a prior ticket; eval uses a fresh store → expected FAIL |
| 027 | Thread continuation needs fixture 002 loaded first; eval does not chain |

---

## Audit notes (for rewriting scenarios)

- Many bodies are **lab telegraphic** (`INV-2026-OVERDUE 500 EUR is late.`, `Pay now`) — good for rules/eval, weak as realistic supplier mail.
- Some scenarios **overlap** (010 ≈ 026; 002 vs 013/014 mainly change intent).
- SAP data behind matches lives in `fixtures/sap_mock/approval.json` and `posted.json`.
- Draft target rules are deterministic in `app/graph/nodes/draft.py` (`pick_target`), not chosen by the LLM.

---

## Related

- Live run against API + Celery (actual outcomes): [EMAIL_FIXTURES_LIVE_RUN.md](EMAIL_FIXTURES_LIVE_RUN.md)
- Outcome diagram: [diagrams/LAB_CALL_DIAGRAMS.md](diagrams/LAB_CALL_DIAGRAMS.md) §4
- Fixture format: [../fixtures/emails/README.md](../fixtures/emails/README.md)
- Eval: `python scripts/run_eval.py`
