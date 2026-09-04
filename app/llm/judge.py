"""Optional draft-text check. Live LLM only when EVAL_LIVE_LLM is set."""

from __future__ import annotations


def judge_draft(expected_text: str | None, actual_text: str | None, *, live: bool = False) -> bool:
    """Compare draft bodies. Live judging is out of default CI."""
    del live
    if not expected_text:
        return not actual_text
    if not actual_text:
        return False
    return expected_text.strip() == actual_text.strip()
