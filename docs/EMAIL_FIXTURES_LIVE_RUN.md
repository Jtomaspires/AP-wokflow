# Live fixture run — actual outcomes

**When:** 2026-10-14  
**How:** Cleared DB, posted all 30 fixtures from `fixtures/emails/` to `POST /webhook/mock`, Celery + live OpenAI.  
**Compared to:** each fixture’s `expected` block (designed for golden eval with `FixtureGuidedLLM` + `eval_date` = email `received_at`).

**Headline:** 82/112 expected fields matched. Several mismatches are **environment**, not “broken SAP rules”.

---

## Summary for evaluation

| Bucket | Count | Meaning |
|---|---|---|
| Fully aligned with expected | ~16 | Early stops + clear SAP cases |
| Draft target shifted (sender → approval_owners) | many on `INV-2026-0001` | Live clock is **2026-10-14**; due date is **2026-09-15** → overdue. Golden eval freezes date via `eval_date`. |
| LLM triage/extraction differed | 002, 005, 023 | Real model ≠ `FixtureGuidedLLM` |
| SPF/DKIM quarantine skipped | 017 | `SPF_DKIM_ENABLED=false` in settings |
| No new ticket row | 021, 022 | Content-hash duplicate of 002 (same subject+body) — **correct** in a shared DB |
| Thread merge | 027 | New row `discarded`; body merged into 002’s ticket — **correct** thread behaviour |

---

## Results table

| # | Name | Actual status | Resolution | Draft → to | Proof | vs expected |
|---|---|---|---|---|---|---|
| **001** | invoice_not_found | `awaiting_human` | not_found | `invoicing` → `invoicing@company.com` | no | status✓ res✓ draft✓ to✓ |
| **002** | in_approval_on_time | `awaiting_human` | not_found | `invoicing` → `invoicing@company.com` | no | status✓ res✗ draft✗ to✗ |
| **003** | posted_paid_clearing | `awaiting_human` | match | `sender` → `billing@acme-supplies.com` | yes | all ✓ |
| **004** | unknown_domain_quarantine | `quarantined` | — | — | — | all ✓ |
| **005** | not_ap_discard | `awaiting_human` | not_found | `invoicing` → `invoicing@company.com` | no | all ✗ (LLM kept as AP) |
| **006** | delegate_other_operator | `delegated` | — | — | — | all ✓ |
| **007** | vat_discrepancy | `awaiting_human` | vat_discrepancy | — | — | all ✓ |
| **008** | multiple_sources | `awaiting_human` | multiple | — | — | all ✓ |
| **009** | posted_blocked | `awaiting_human` | match | `payments` → `payments@company.com` | no | all ✓ |
| **010** | in_approval_overdue_owner | `awaiting_human` | match | `approval_owners` → `ap-owner@company.com` | no | all ✓ |
| **011** | unknown_intent | `awaiting_human` | not_found | `invoicing` → `invoicing@company.com` | no | all ✓ |
| **012** | low_confidence_intent | `awaiting_human` | not_found | `invoicing` → `invoicing@company.com` | no | all ✓ |
| **013** | delay_reason | `awaiting_human` | match | `approval_owners` → `ap-owner@company.com` | no | draft/to ✗ (overdue vs eval date) |
| **014** | future_timing | `awaiting_human` | match | `approval_owners` → `ap-owner@company.com` | no | draft/to ✗ (same) |
| **015** | fuzzy_ref | `awaiting_human` | multiple | — | — | all ✓ |
| **016** | amount_supplier_match | `awaiting_human` | match | `approval_owners` → `ap-owner@company.com` | no | draft/to ✗ (matched overdue invoice) |
| **017** | spf_dkim_fail | `awaiting_human` | match | `approval_owners` → `ap-owner@company.com` | no | SPF check off → not quarantined |
| **018** | posted_partial | `awaiting_human` | match | `sender` → `billing@acme-supplies.com` | no | all ✓ |
| **019** | paid_no_clearing | `awaiting_human` | match | — | — | all ✓ (no draft) |
| **020** | overdue_no_owner | `awaiting_human` | match | — | — | all ✓ (no draft) |
| **021** | spf_only_fail_penalty | *(no new ticket)* | — | — | — | content_duplicate of **002** |
| **022** | content_duplicate_resubmit | *(no new ticket)* | — | — | — | content_duplicate of **002** ✓ for shared DB |
| **023** | low_extraction_confidence | `awaiting_human` | match | `sender` → `billing@acme-supplies.com` | yes | LLM extracted enough to match |
| **024** | multilingual_portuguese | `awaiting_human` | match | `approval_owners` → `ap-owner@company.com` | no | draft/to ✗ (overdue clock) |
| **025** | adversarial_prompt_injection | `awaiting_human` | match | `approval_owners` → `ap-owner@company.com` | no | draft/to ✗; injection ignored ✓ |
| **026** | overdue_invoice_in_approval | `awaiting_human` | match | `approval_owners` → `ap-owner@company.com` | no | all ✓ |
| **027** | thread_continuation_context | `discarded` | — | — | — | merged into **002** (thread) |
| **028** | amount_mismatch_tolerance_edge | `awaiting_human` | match | `approval_owners` → `ap-owner@company.com` | no | draft/to ✗ (overdue clock) |
| **029** | spam_like_ap_content | `awaiting_human` | not_found | `invoicing` → `invoicing@company.com` | no | all ✓ |
| **030** | subsidiary_domain_whitelisted | `awaiting_human` | match | `sender` → `ap@group-subsidiary.com` | yes | all ✓ |

---

## What this means for rewriting scenarios

1. **Bodies/subjects feel like lab fixtures**, not supplier mail — still true; rewriting copy does not fix clock/`eval_date` issues.
2. **Demo vs golden:** live UI uses **today** for overdue. Fixtures dated Sept 2026 behave as overdue in Oct 2026. For demo emails about “on-time approval”, use a due date in the future in SAP mock, or accept approval_owners.
3. **005 “Team lunch”** is fragile with a real LLM — often stays AP → invoicing. Need a clearer non-AP email if you want a reliable discard demo.
4. **017** will not quarantine until `SPF_DKIM_ENABLED=true`.
5. **021/022** prove content dedup works on a shared DB (audit `content_duplicate` on ticket 002). Golden eval still fails 022 on purpose because each fixture gets a fresh store.
6. Strong demo cases that matched live: **003** paid+clearing, **004** quarantine, **006** delegate, **009** blocked→payments, **010/026** overdue→owner, **018** partial, **019** paid no clearing, **030** subsidiary domain.

---

## Related

- Expected inventory: [EMAIL_FIXTURES.md](EMAIL_FIXTURES.md)
- Outcome rules: [diagrams/LAB_CALL_DIAGRAMS.md](diagrams/LAB_CALL_DIAGRAMS.md) §4
