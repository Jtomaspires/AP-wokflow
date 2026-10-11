"""OpenAI adapter behaviour with the HTTP client stubbed (no network)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest

from app.adapters.openai_llm import LLMOutputError, LLMRefusalError, OpenAILLMAdapter
from app.domain.schemas import TriageOutput


def _completion(*, parsed=None, refusal=None):
    message = SimpleNamespace(parsed=parsed, refusal=refusal)
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def _adapter(**kwargs) -> OpenAILLMAdapter:
    return OpenAILLMAdapter(api_key="sk-test", model="gpt-test", retry_backoff_s=0, **kwargs)


def _timeout() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=httpx.Request("POST", "https://api.test"))


async def _generate(adapter: OpenAILLMAdapter):
    return await adapter.generate(system_prompt="s", user_prompt="u", output_schema=TriageOutput)


async def test_returns_parsed_output_and_records_usage():
    adapter = _adapter()
    expected = TriageOutput(is_ap=True, confidence=0.9)
    adapter._client.chat.completions.parse = AsyncMock(return_value=_completion(parsed=expected))

    assert await _generate(adapter) == expected
    assert adapter.calls == [
        {"schema": "TriageOutput", "model": "gpt-test", "prompt_tokens": 10, "completion_tokens": 5}
    ]


async def test_refusal_raises():
    adapter = _adapter()
    adapter._client.chat.completions.parse = AsyncMock(return_value=_completion(refusal="no"))
    with pytest.raises(LLMRefusalError):
        await _generate(adapter)


async def test_missing_parsed_output_raises():
    adapter = _adapter()
    adapter._client.chat.completions.parse = AsyncMock(return_value=_completion())
    with pytest.raises(LLMOutputError):
        await _generate(adapter)


async def test_retries_once_on_timeout():
    adapter = _adapter()
    expected = TriageOutput(is_ap=False, confidence=0.4)
    adapter._client.chat.completions.parse = AsyncMock(
        side_effect=[_timeout(), _completion(parsed=expected)]
    )
    assert await _generate(adapter) == expected
    assert adapter._client.chat.completions.parse.await_count == 2


async def test_falls_back_after_second_timeout():
    fallback = _adapter()
    expected = TriageOutput(is_ap=True, confidence=0.7)
    fallback._client.chat.completions.parse = AsyncMock(return_value=_completion(parsed=expected))
    adapter = _adapter(fallback=fallback)
    adapter._client.chat.completions.parse = AsyncMock(side_effect=[_timeout(), _timeout()])

    assert await _generate(adapter) == expected


def test_default_llm_is_mock_without_key(monkeypatch):
    from app.adapters.mock_llm import MockLLMAdapter
    from app.api import deps

    monkeypatch.setattr(deps.settings, "LLM_PRIMARY_API_KEY", None)
    assert isinstance(deps._default_llm(), MockLLMAdapter)


def test_default_llm_is_openai_with_key(monkeypatch):
    from app.api import deps

    monkeypatch.setattr(deps.settings, "LLM_PRIMARY_API_KEY", "sk-test")
    monkeypatch.setattr(deps.settings, "LLM_FALLBACK_MODEL", None)
    assert isinstance(deps._default_llm(), OpenAILLMAdapter)


async def test_raises_after_second_timeout_without_fallback():
    adapter = _adapter()
    adapter._client.chat.completions.parse = AsyncMock(side_effect=[_timeout(), _timeout()])
    with pytest.raises(openai.APITimeoutError):
        await _generate(adapter)
