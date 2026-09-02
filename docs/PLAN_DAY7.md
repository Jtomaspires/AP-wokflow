# Day 7 — Post-parity improvements (not in the original assistant)

> Do this **after** Days 3–6 match `p2p-ai-assistant`. These items are **new**.
>
> Previous: [PLAN_DAY6.md](PLAN_DAY6.md). Charter: [README.md](README.md).

**Status:** planned.

Keep Streamlit out. Default eval (Day 6) should still be able to run with the retry **disabled**.

---

## 7.1 Resolution correction loop

If the **first** match ladder (Day 5: exact → fuzzy ≥ 0.85 → amount ± tolerance + supplier) does not yield a unique, high-confidence invoice:

1. Run the Day 5 ladder unchanged.
2. If result is miss / ambiguous **and** match confidence &lt; `RESOLUTION_RETRY_MIN_CONFIDENCE` → **do not** go straight to HITL.
3. Widen tolerances **once** (hard cap, default `RESOLUTION_RETRY_MAX=1`): e.g. multiply `MATCH_VALUE_TOLERANCE_PCT` / `ABS`, and/or lower fuzzy cutoff to a documented floor (do not drop without a floor).
4. Re-run the ladder. Audit: `retry_n`, old vs new thresholds, previous vs new `InvoiceMatchResult`.
5. If still not unique/high-conf → same HITL path as Day 5 (`requires_hitl` / no draft).

Settings (names may vary; document in `settings.py`):

- `RESOLUTION_RETRY_ENABLED` (default `False` until Day 7 ships; eval uses `False`)
- `RESOLUTION_RETRY_MIN_CONFIDENCE`
- `RESOLUTION_RETRY_MAX` = 1
- multipliers / fuzzy floor

Tests (`tests/test_node_resolution_retry.py`):

- [ ] Low-confidence fuzzy miss that **succeeds** after wider amount tolerance → unique match, no extra HITL
- [ ] Still fail after retry → `requires_hitl` as today
- [ ] Cap: second retry does not run
- [ ] Audit contains retry metadata

Do not turn this into an unbounded graph cycle (`resolution` → `resolution`). Keep the loop **inside** the resolution node.

---

## 7.2 Visual root README

Create **English** root [`README.md`](../README.md) (Day 2 DoD may only have a stub):

- [ ] What the project is (LangGraph P2P assistant, no Streamlit)
- [ ] Embedded **architecture / workflow** diagram: draw in **Excalidraw or Eraser**, export SVG or PNG to `docs/assets/`, embed in README (in addition to Mermaid/draw.io call diagrams)
- [ ] Short **GIF** of the happy path: webhook → graph → `AWAITING_HUMAN` → approve → send. Screen recording or generated animation; store `docs/assets/happy-path.gif` (or `.webp` if GitHub renders it)
- [ ] How to run: `docker compose up -d`, `alembic upgrade head`, uvicorn, Celery `--pool=solo` on Windows, sample `curl` for `/webhook/mock` and `/tickets/{id}/approve`
- [ ] Link to `docs/PLAN_DAY*.md` and `docs/diagrams/LAB_CALL_DIAGRAMS.md`

### Definition of Done — visuals

- [ ] README can be skimmed without reading day plans
- [ ] GIF + diagram render on GitHub
- [ ] No Streamlit screenshots required (API/curl or terminal is enough)

---

## Definition of Done — Day 7

- [ ] Retry loop implemented and tested; off by default for parity eval
- [ ] Root README is visual and English
- [ ] Days 3–6 behaviour unchanged when retry is disabled

---

## Still out of scope

Streamlit, OCR, live Nylas/SAP, auto-send, copying Launchpad `core/`.
