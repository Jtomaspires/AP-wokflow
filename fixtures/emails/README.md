# Email golden set (Day 6)

Assistant-style `input` + `expected` JSON. Each fixture opens a fresh store. `depends_on` is not chained, so `022` cannot see the hash from `002` and is not a golden proof of dedup (`tests/test_node_ingest.py` is). A workflow field omitted from `expected` is not scored; an explicit `null` is.

LLM fields (`is_ap`, `intent`, `extracted_*`, `generated_text`) drive `FixtureGuidedLLM`. Workflow fields (`ticket_status`, `invoice_resolution`, `draft_target`, …) are scored after `build_graph(deps).ainvoke`.

`draft_checks` (only on fixtures that produce a draft) feeds `judge_draft`: every `required_tokens` entry must appear in the draft text and no `forbidden_tokens` entry may appear (case-insensitive). It lets a real model word the reply freely while still catching a missing invoice ref or a false "has been paid". The judge result is reported as `draft_judge` and is not part of `workflow_ok`. Edit `scripts/write_email_fixtures.py` and regenerate rather than editing the JSON by hand.
