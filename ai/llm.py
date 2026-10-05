"""Groq plumbing shared by the LangGraph flows.

Graphs take an `LLM` callable instead of a Groq client, so tests can pass a
fake and exercise every branch (partial failure, retries, abstention)
without network calls or API keys.
"""
import os
from typing import Awaitable, Callable, Optional

# (model, messages, max_tokens, temperature) -> response text
LLM = Callable[[str, list[dict], int, float], Awaitable[str]]


def configured_groq_key() -> Optional[str]:
    """Returns GROQ_API_KEY, or None if it's unset or still a placeholder
    value (any '.env.example' entry starts with 'your_')."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        return None
    return api_key


def reasoning_kwargs(model: str) -> dict:
    """Groq's current chat models (gpt-oss, qwen3.8) are reasoning models by
    default — left alone, they spend max_tokens on invisible chain-of-thought
    and can return empty content. Pin them to minimal/no reasoning so
    max_tokens goes to the actual answer instead. Param names/values are
    model-family-specific per Groq's API."""
    if model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low", "reasoning_format": "hidden"}
    if model.startswith("qwen/"):
        return {"reasoning_effort": "none"}
    return {}


def make_groq_llm(api_key: str, timeout: float = 30.0) -> LLM:
    """Native async client, so parallel graph branches are real concurrent
    HTTP requests on the event loop — no thread-pool hop per call. One
    retry with a short timeout: a retired or overloaded model should fail
    fast so the graph can route around it, not hang the request."""
    from groq import AsyncGroq
    client = AsyncGroq(api_key=api_key, timeout=timeout, max_retries=1)

    async def call(model: str, messages: list[dict], max_tokens: int, temperature: float) -> str:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **reasoning_kwargs(model),
        )
        return (resp.choices[0].message.content or "").strip()

    return call
