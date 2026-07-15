"""Shared OpenAI-compatible LLM client factory (OpenAI, Groq, …).

Groq (and many other providers) expose an OpenAI-compatible chat API. We reuse the
``openai`` Python SDK and only swap ``base_url`` + API key env var per backend.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LlmProvider:
    name: str
    base_url: str | None  # None = OpenAI default endpoint
    api_key_env: str
    default_model: str


PROVIDERS: dict[str, LlmProvider] = {
    "openai": LlmProvider(
        name="openai",
        base_url=None,
        api_key_env="OPENAI_API_KEY",
        default_model="gpt-4o-mini",
    ),
    "groq": LlmProvider(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        default_model="llama-3.3-70b-versatile",
    ),
}

# Backends that call a remote LLM (vs local extractive analysis).
REMOTE_LLM_BACKENDS = frozenset(PROVIDERS)


def resolve_provider(backend: str) -> LlmProvider:
    key = (backend or "").strip().lower()
    if key not in PROVIDERS:
        raise ValueError(
            f"Unknown LLM backend {backend!r}. Supported: {sorted(PROVIDERS)} "
            f"(or 'deterministic' for offline extractive mode)."
        )
    return PROVIDERS[key]


def build_chat_client(backend: str, *, client=None):
    """Return an OpenAI-SDK client pointed at the chosen provider.

    ``client`` may be injected for tests. Requires the ``openai`` package and the
    provider's API key in the environment.
    """
    if client is not None:
        return client

    provider = resolve_provider(backend)
    api_key = os.environ.get(provider.api_key_env)
    if not api_key:
        raise RuntimeError(
            f"{provider.api_key_env} is not set. Get a key and export it, e.g. "
            f"`export {provider.api_key_env}=...` before using backend={provider.name!r}."
        )
    try:
        from openai import OpenAI  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "The `openai` package is required for remote LLM backends. "
            "Install with: pip install openai"
        ) from exc
    kwargs = {"api_key": api_key}
    if provider.base_url:
        kwargs["base_url"] = provider.base_url
    return OpenAI(**kwargs)


def default_model_for(backend: str, configured: str | None = None) -> str:
    """Prefer an explicit model; otherwise the provider default."""
    if configured and configured.strip():
        # Avoid silently sending an OpenAI model name to Groq.
        if backend == "groq" and configured.startswith("gpt-"):
            return resolve_provider(backend).default_model
        return configured
    return resolve_provider(backend).default_model
