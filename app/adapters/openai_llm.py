"""OpenAI structured-output adapter for LLMPort."""

from __future__ import annotations

import asyncio
from typing import Any

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.ports.llm_port import LLMPort

_RETRYABLE = (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError)


class LLMRefusalError(RuntimeError):
    pass


class LLMOutputError(RuntimeError):
    pass


class OpenAILLMAdapter(LLMPort):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout_s: int = 15,
        retry_backoff_s: int = 2,
        fallback: OpenAILLMAdapter | None = None,
    ) -> None:
        # Per instance: the worker runs asyncio.run() per task, and an async
        # client shared across event loops fails on the second task.
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s)
        self._model = model
        self._retry_backoff_s = retry_backoff_s
        self._fallback = fallback
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[BaseModel],
    ) -> BaseModel:
        try:
            return await self._parse(system_prompt, user_prompt, output_schema)
        except _RETRYABLE:
            await asyncio.sleep(self._retry_backoff_s)
            try:
                return await self._parse(system_prompt, user_prompt, output_schema)
            except _RETRYABLE:
                if self._fallback is None:
                    raise
                return await self._fallback.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=output_schema,
                )

    async def _parse(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[BaseModel],
    ) -> BaseModel:
        completion = await self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=output_schema,
        )
        usage = completion.usage
        self.calls.append(
            {
                "schema": output_schema.__name__,
                "model": self._model,
                "prompt_tokens": usage.prompt_tokens if usage else None,
                "completion_tokens": usage.completion_tokens if usage else None,
            }
        )
        message = completion.choices[0].message
        if message.refusal:
            raise LLMRefusalError(message.refusal)
        if message.parsed is None:
            raise LLMOutputError(f"no parsed output for {output_schema.__name__}")
        return message.parsed
