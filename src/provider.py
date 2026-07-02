"""
Unified LLM client for the SEODOMINATOR pipeline.

Auto-detects provider from the first key found (priority order):
  1. ANTHROPIC_API_KEY  → Claude (prompt caching supported natively)
  2. XAI_API_KEY        → Grok  (OpenAI-compatible endpoint at api.x.ai)
  3. OPENAI_API_KEY     → GPT-4o

Override via env vars:
  LLM_PROVIDER=xai          # force a specific provider
  LLM_MODEL=grok-3-mini     # force a specific model

Usage in pipeline stages:
    from src.provider import LLMClient, get_llm_client
    self._client = get_llm_client(self._settings)
    response = self._client.messages.create(
        model=self._client.model, system=[...], messages=[...], max_tokens=512
    )
    text   = response.content[0].text
    t_in   = response.usage.input_tokens
    t_out  = response.usage.output_tokens
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "xai":       "grok-3",
    "openai":    "gpt-4o",
}

_XAI_BASE_URL = "https://api.x.ai/v1"

_KEY_PRIORITY = [
    ("anthropic_api_key", "ANTHROPIC_API_KEY", "anthropic"),
    ("xai_api_key",       "XAI_API_KEY",       "xai"),
    ("openai_api_key",    "OPENAI_API_KEY",     "openai"),
]


# ── Response shim for non-Anthropic providers ─────────────────────────────────

class _Block:
    __slots__ = ("text",)
    def __init__(self, text: str): self.text = text

class _Usage:
    __slots__ = ("input_tokens", "output_tokens")
    def __init__(self, tin: int, tout: int):
        self.input_tokens = tin
        self.output_tokens = tout

class _Response:
    """Anthropic-shaped response for OpenAI-compatible providers."""
    def __init__(self, text: str, tin: int, tout: int):
        self.content = [_Block(text)]
        self.usage   = _Usage(tin, tout)


# ── Messages adapters ─────────────────────────────────────────────────────────

class _AnthropicMessages:
    def __init__(self, client):
        self._c = client

    def create(self, *, model: str, system, messages, max_tokens: int, **kwargs):
        return self._c.messages.create(
            model=model, system=system, messages=messages,
            max_tokens=max_tokens, **kwargs
        )


class _OpenAICompatMessages:
    """Adapts OpenAI chat.completions API to look like Anthropic's messages API.

    Strips Anthropic-specific fields (cache_control) from content blocks so the
    same pipeline stage code works without modification.
    """
    def __init__(self, client):
        self._c = client

    @staticmethod
    def _to_text(blocks) -> str:
        if isinstance(blocks, str):
            return blocks
        return "\n".join(b.get("text", "") for b in blocks if isinstance(b, dict))

    def create(self, *, model: str, system, messages, max_tokens: int, **kwargs):
        oai_msgs = [{"role": "system", "content": self._to_text(system)}]
        for msg in messages:
            oai_msgs.append({"role": msg["role"], "content": self._to_text(msg["content"])})
        # Pass through supported OpenAI params (temperature, top_p, etc.)
        oai_kwargs = {k: v for k, v in kwargs.items() if k in ("temperature", "top_p", "presence_penalty", "frequency_penalty")}
        resp = self._c.chat.completions.create(model=model, messages=oai_msgs, max_tokens=max_tokens, **oai_kwargs)
        text = resp.choices[0].message.content
        return _Response(text, resp.usage.prompt_tokens, resp.usage.completion_tokens)


# ── Public API ────────────────────────────────────────────────────────────────

@dataclass
class LLMClient:
    """Unified LLM client — Anthropic-compatible interface regardless of provider."""
    messages: object
    model:    str
    provider: str


def get_llm_client(settings=None) -> LLMClient:
    """Return an LLMClient for whichever provider is configured.

    Reads keys from *settings* (Settings dataclass) first, env vars as fallback.
    Respects LLM_PROVIDER and LLM_MODEL env-var overrides.
    """
    forced_provider = (os.getenv("LLM_PROVIDER") or "").lower() or None
    forced_model    = os.getenv("LLM_MODEL") or None

    def _key(attr: str, env: str) -> str:
        return (getattr(settings, attr, "") or os.getenv(env, "")) or ""

    if forced_provider:
        row = next((t for t in _KEY_PRIORITY if t[2] == forced_provider), None)
        if row is None:
            raise EnvironmentError(
                f"Unknown LLM_PROVIDER '{forced_provider}'. Choose: anthropic, xai, openai."
            )
        provider_name, api_key = row[2], _key(row[0], row[1])
    else:
        provider_name, api_key = None, None
        for attr, env, name in _KEY_PRIORITY:
            k = _key(attr, env)
            if k:
                provider_name, api_key = name, k
                break
        if provider_name is None:
            raise EnvironmentError(
                "No LLM key found. Set ANTHROPIC_API_KEY, XAI_API_KEY, or OPENAI_API_KEY."
            )

    model = forced_model or _DEFAULT_MODELS[provider_name]

    if provider_name == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        return LLMClient(messages=_AnthropicMessages(client), model=model, provider=provider_name)

    import openai as _openai
    base_url = _XAI_BASE_URL if provider_name == "xai" else None
    client = _openai.OpenAI(api_key=api_key, base_url=base_url)
    return LLMClient(messages=_OpenAICompatMessages(client), model=model, provider=provider_name)
