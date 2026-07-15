"""LLM provider resolution (OpenAI / Groq)."""

import os

import pytest

from pulse.reasoning.providers import (
    REMOTE_LLM_BACKENDS,
    build_chat_client,
    default_model_for,
    resolve_provider,
)


def test_groq_provider_defaults():
    p = resolve_provider("groq")
    assert p.base_url == "https://api.groq.com/openai/v1"
    assert p.api_key_env == "GROQ_API_KEY"
    assert default_model_for("groq", None) == "llama-3.3-70b-versatile"
    # Don't send an OpenAI model name to Groq by accident.
    assert default_model_for("groq", "gpt-4o-mini") == "llama-3.3-70b-versatile"
    assert default_model_for("groq", "llama-3.1-8b-instant") == "llama-3.1-8b-instant"


def test_openai_and_groq_are_remote():
    assert "openai" in REMOTE_LLM_BACKENDS and "groq" in REMOTE_LLM_BACKENDS


def test_missing_groq_key_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        build_chat_client("groq")


def test_injected_client_bypasses_env():
    class Fake:
        pass

    assert build_chat_client("groq", client=Fake()) is not None
