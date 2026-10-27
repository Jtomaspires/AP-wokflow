"""Token-based draft check: required tokens present, forbidden tokens absent."""

from __future__ import annotations


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
