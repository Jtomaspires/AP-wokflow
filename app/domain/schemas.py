"""Structured LLM output schemas (not persisted)."""

from pydantic import BaseModel


class TriageOutput(BaseModel):
    is_ap: bool
    confidence: float
