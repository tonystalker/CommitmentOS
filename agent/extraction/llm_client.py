"""CommitmentOS — Swappable LLM client abstraction.

Supports Groq, OpenRouter, OpenAI, and Anthropic via LLM_PROVIDER env var.
Allows switching providers dynamically without code modifications.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from openai import AsyncOpenAI

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    provider: str
    model: str
    client: AsyncOpenAI
    fallback_models: list[str]


_cached_configs: dict[str, LLMConfig] = {}


def get_llm_config() -> LLMConfig:
    """Return the LLM configuration and client based on LLM_PROVIDER."""
    provider = (
        os.getenv("LLM_PROVIDER")
        or getattr(settings, "llm_provider", "groq")
        or "groq"
    ).lower().strip()

    # Allow dynamic reload if provider changes
    cached = _cached_configs.get(provider)
    if cached is not None:
        return cached

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY") or getattr(settings, "groq_api_key", "")
        base_url = "https://api.groq.com/openai/v1"
        model = (
            os.getenv("GROQ_MODEL")
            or getattr(settings, "groq_model", "")
            or "llama-3.3-70b-versatile"
        )
        # Verify preferred model on Groq; fallback chain if 404
        fallbacks = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
        client = AsyncOpenAI(
            api_key=api_key or "placeholder",
            base_url=base_url,
        )
    elif provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or getattr(settings, "openai_api_key", "")
        base_url = os.getenv("OPENAI_BASE_URL") or getattr(settings, "openai_base_url", "https://openrouter.ai/api/v1")
        model = os.getenv("OPENROUTER_MODEL") or os.getenv("OPENAI_MODEL") or getattr(settings, "openai_model", "nex-agi/nex-n2.5-mini:free")
        fallbacks = [model, "nex-agi/nex-n2.5-mini:free"]
        client = AsyncOpenAI(
            api_key=api_key or "placeholder",
            base_url=base_url,
            default_headers={"HTTP-Referer": "http://localhost:3000", "X-Title": "CommitmentOS"},
        )
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "openai_api_key", "")
        base_url = os.getenv("OPENAI_BASE_URL") or getattr(settings, "openai_base_url", None)
        model = os.getenv("OPENAI_MODEL") or getattr(settings, "openai_model", "gpt-4o-mini")
        fallbacks = [model, "gpt-4o-mini"]
        client = AsyncOpenAI(api_key=api_key or "placeholder", base_url=base_url)
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY") or ""
        base_url = os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com/v1"
        model = os.getenv("ANTHROPIC_MODEL") or "claude-3-5-sonnet-20241022"
        fallbacks = [model]
        client = AsyncOpenAI(api_key=api_key or "placeholder", base_url=base_url)
    else:
        # Generic OpenAI-compatible
        api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "openai_api_key", "")
        base_url = os.getenv("OPENAI_BASE_URL") or getattr(settings, "openai_base_url", None)
        model = os.getenv("OPENAI_MODEL") or getattr(settings, "openai_model", "gpt-4o-mini")
        fallbacks = [model]
        client = AsyncOpenAI(api_key=api_key or "placeholder", base_url=base_url)

    cfg = LLMConfig(provider=provider, model=model, client=client, fallback_models=fallbacks)
    _cached_configs[provider] = cfg
    logger.info("Initialized LLM provider '%s' with model '%s'", provider, model)
    return cfg


def get_llm_client() -> tuple[AsyncOpenAI, str]:
    """Convenience helper returning (client, model) for the configured provider."""
    cfg = get_llm_config()
    return cfg.client, cfg.model
