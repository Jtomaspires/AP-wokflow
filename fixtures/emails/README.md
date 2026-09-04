# Email golden set (Day 6)

Assistant-style `input` + `expected` JSON. Each case is a **new** ticket (unique `message_id`); thread continuation is not evaluated here.

LLM fields (`is_ap`, `intent`, `extracted_*`, `generated_text`) drive `FixtureGuidedLLM`. Workflow fields (`ticket_status`, `invoice_resolution`, `draft_target`, …) are scored after `build_graph(deps).ainvoke`.
