"""Groq LLM provider with streaming support.

Uses the Groq API (OpenAI-compatible) for fast inference on open-source
models like Llama 3 and Mixtral.

Both synchronous ``generate()`` and streaming ``generate_stream()`` are
implemented.  The streaming path uses Server-Sent Events for real-time
token delivery.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

# Groq API uses the OpenAI-compatible chat completions endpoint
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqLLMProvider:
    """LLM provider backed by Groq's inference API.

    Implements the ``LLMProvider`` protocol defined in ``domain.interfaces``.
    """

    def __init__(self, api_key: str, model_id: str = "llama-3.3-70b-versatile") -> None:
        self._api_key = api_key
        self._model_id = model_id
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        logger.info("GroqLLMProvider initialised (model=%s)", model_id)

    # ------------------------------------------------------------------
    # Synchronous generation
    # ------------------------------------------------------------------

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.4,
    ) -> str:
        """Generate a complete response (non-streaming)."""
        payload = self._build_payload(system_prompt, messages, max_tokens, temperature, stream=False)

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    GROQ_API_URL,
                    headers=self._headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                text = data["choices"][0]["message"]["content"]
                return text.strip()
            except httpx.HTTPStatusError as exc:
                logger.error("Groq API error (status=%s): %s", exc.response.status_code, exc.response.text)
                raise RuntimeError(f"Groq API error: {exc.response.status_code}") from exc
            except Exception as exc:
                logger.error("Groq generate failed: %s", exc)
                raise

    # ------------------------------------------------------------------
    # Streaming generation
    # ------------------------------------------------------------------

    async def generate_stream(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.4,
    ) -> AsyncIterator[str]:
        """Stream response tokens using Groq's streaming API (SSE)."""
        payload = self._build_payload(system_prompt, messages, max_tokens, temperature, stream=True)

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream(
                    "POST",
                    GROQ_API_URL,
                    headers=self._headers,
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        logger.error("Groq streaming error (status=%s): %s", response.status_code, body.decode())
                        yield "I'm unable to connect to the AI service right now. Please try again."
                        return

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[len("data: "):]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            continue

            except httpx.HTTPStatusError as exc:
                logger.error("Groq streaming HTTP error: %s", exc)
                yield "I encountered an error while generating the response. Please try again."
            except Exception as exc:
                logger.error("Unexpected Groq streaming error: %s", exc)
                yield "An unexpected error occurred. Please try again."

    # ------------------------------------------------------------------
    # Request payload builder
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        stream: bool = False,
    ) -> dict:
        """Build the OpenAI-compatible chat completion payload."""
        api_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            api_messages.append({
                "role": m["role"],
                "content": m["content"],
            })

        return {
            "model": self._model_id,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
            "stream": stream,
        }
