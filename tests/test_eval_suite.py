from pathlib import Path

import pytest

from scripts.eval_harness import DIMENSIONS, load_fixtures, run_fixture


def test_twenty_golden_fixtures_present():
    paths = load_fixtures()
    assert len(paths) == 20
    stems = {p.name[:3] for p in paths}
    assert stems == {f"{i:03d}" for i in range(1, 21)}


def test_harness_does_not_import_ui_or_launchpad():
    src = Path("scripts/eval_harness.py").read_text(encoding="utf-8")
    assert "import streamlit" not in src
    assert "from streamlit" not in src
    assert "TicketWorkflow" not in src
    assert "ainvoke" in src
    assert "build_graph" in src


@pytest.mark.asyncio
async def test_not_found_and_quarantine_smoke():
    fixtures = {p.name: p for p in load_fixtures()}
    missing = await run_fixture(fixtures["001_invoice_not_found.json"])
    assert missing["workflow_ok"] is True
    assert missing["actual"]["invoice_resolution"] == "not_found"
    assert missing["actual"]["ticket_status"] == "awaiting_human"
    assert set(missing["dimensions"]) == set(DIMENSIONS)

    quarantined = await run_fixture(fixtures["004_unknown_domain_quarantine.json"])
    assert quarantined["workflow_ok"] is True
    assert quarantined["actual"]["ticket_status"] == "quarantined"
    assert quarantined["llm_calls"] == []
