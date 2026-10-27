"""Token-based draft judge."""

from app.llm.judge import judge_draft

CHECKS = {"required_tokens": ["INV-2026-0001"], "forbidden_tokens": ["has been paid"]}


def test_passes_when_required_present_and_forbidden_absent():
    assert judge_draft(CHECKS, "We are reviewing invoice INV-2026-0001.", expect_draft=True)


def test_fails_when_required_token_missing():
    assert not judge_draft(CHECKS, "We are reviewing your invoice.", expect_draft=True)


def test_fails_when_forbidden_token_present():
    text = "Invoice INV-2026-0001 has been paid."
    assert not judge_draft(CHECKS, text, expect_draft=True)


def test_is_case_insensitive():
    assert judge_draft(CHECKS, "invoice inv-2026-0001 is in approval", expect_draft=True)
    assert not judge_draft(CHECKS, "INV-2026-0001 HAS BEEN PAID", expect_draft=True)


def test_no_draft_expected_and_none_produced():
    assert judge_draft(None, None, expect_draft=False)


def test_draft_expected_but_none_produced():
    assert not judge_draft(CHECKS, None, expect_draft=True)
    assert not judge_draft(CHECKS, "", expect_draft=True)


def test_draft_produced_when_none_expected():
    assert not judge_draft(None, "Unexpected reply", expect_draft=False)


def test_missing_checks_accepts_any_non_empty_draft():
    assert judge_draft(None, "Any reply", expect_draft=True)
