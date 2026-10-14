"""Turn a stored AgentConfig into what the agent graph actually runs on.

Two concerns live here because both mix stored config with the environment:

- LLM resolution. An agent's `llm` block overrides `config.yaml`, but its API
  key always comes from an environment variable named for the provider, so
  secrets never land in the database.
- Pipeline resolution. An agent may point at a Pipeline Builder pipeline; it is
  only used while it is still active and still belongs to this agent.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import LlmSection, get_settings
from app.db.models import Pipeline, PipelineStatus, Service, SystemPrompt
from app.schemas.agent_config import AgentConfig

logger = logging.getLogger(__name__)

# Where each hosted provider's key is read from. A provider that matches
# config.yaml's default may also use LLM_API_KEY, which is how a single-provider
# deployment keeps working with no new variables.
PROVIDER_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}

# Shown as suggestions in the settings UI. Ollama's list comes from the local
# server instead, since it is whatever the user has pulled.
SUGGESTED_MODELS: dict[str, list[str]] = {
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "anthropic": ["claude-haiku-4-5-20251001", "claude-sonnet-5"],
    "google": ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"],
}


def load_agent_config(service: Service | None) -> AgentConfig:
    return AgentConfig.from_stored(service.agent_config if service else None)


def load_system_prompt(db: Session, service_id: int) -> str:
    """The agent's active system prompt, or the config.yaml fallback."""
    row = db.execute(
        select(SystemPrompt).where(SystemPrompt.service_id == service_id, SystemPrompt.is_active.is_(True))
    ).scalar_one_or_none()
    return row.content if row else get_settings().chat.fallback_system_prompt


def _api_key_for(provider: str) -> str | None:
    base = get_settings().llm
    env_name = PROVIDER_KEY_ENV.get(provider)
    key = os.getenv(env_name) if env_name else None
    if not key and provider == base.provider:
        key = base.api_key
    return key


def resolve_llm(agent_cfg: AgentConfig) -> LlmSection:
    """Merge the agent's overrides onto config.yaml's llm section."""
    base = get_settings().llm
    override = agent_cfg.llm
    provider = override.provider or base.provider

    update: dict[str, Any] = {"provider": provider, "api_key": _api_key_for(provider)}
    if override.model:
        update["model"] = override.model
    elif provider != base.provider:
        # The default model belongs to the default provider; borrowing it for a
        # different provider would send e.g. "qwen2.5:14b" to Gemini.
        suggestions = SUGGESTED_MODELS.get(provider) or []
        if not suggestions:
            raise ValueError(f"agent uses provider {provider!r} but sets no model")
        update["model"] = suggestions[0]
    if override.temperature is not None:
        update["temperature"] = override.temperature
    return base.model_copy(update=update)


def resolve_pipeline_graph(db: Session, service_id: int, agent_cfg: AgentConfig) -> dict | None:
    """Return the graph of the agent's pipeline, or None for the built-in chain."""
    if agent_cfg.pipeline_id is None:
        return None
    pipeline = db.get(Pipeline, agent_cfg.pipeline_id)
    if not pipeline or pipeline.service_id != service_id or pipeline.status != PipelineStatus.active:
        # Archiving a pipeline must not break chat — fall back and say so in the log.
        logger.warning(
            "agent %d points at pipeline %s, which is missing or not active; using built-in search",
            service_id,
            agent_cfg.pipeline_id,
        )
        return None
    return pipeline.graph_json


def _ollama_models() -> list[str] | None:
    """Chat models pulled into the local Ollama server, or None if unreachable."""
    base_url = get_settings().llm.ollama.base_url.rstrip("/")
    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    names = (m.get("name", "") for m in resp.json().get("models", []))
    # Embedding models share the same list but can't chat.
    return sorted(n for n in names if n and "embed" not in n)


def _vllm_models() -> list[str] | None:
    """Models a vLLM server is serving, or None if it isn't one.

    Probed rather than assumed: a configured base_url proves nothing — the
    default even points at this backend's own port.
    """
    base_url = get_settings().llm.vllm.base_url.rstrip("/")
    if not base_url:
        return None
    try:
        resp = httpx.get(f"{base_url}/models", timeout=2.0)
        resp.raise_for_status()
        return sorted(m["id"] for m in resp.json().get("data", []) if m.get("id"))
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


def provider_catalog() -> list[dict[str, Any]]:
    """Every provider with whether it can be used right now, and why not.

    The settings UI disables providers that would fail at chat time, so a user
    can't save an agent onto a provider with no key or a stopped server.
    """
    settings = get_settings().llm
    catalog: list[dict[str, Any]] = []

    ollama_models = _ollama_models()
    catalog.append({
        "provider": "ollama",
        "available": ollama_models is not None,
        "reason": None if ollama_models is not None else f"Ollama not reachable at {settings.ollama.base_url}",
        "models": ollama_models or [],
    })

    for provider in ("google", "openai", "anthropic"):
        has_key = bool(_api_key_for(provider))
        catalog.append({
            "provider": provider,
            "available": has_key,
            "reason": None if has_key else f"set {PROVIDER_KEY_ENV[provider]} in .env",
            "models": SUGGESTED_MODELS[provider],
        })

    vllm_models = _vllm_models()
    catalog.append({
        "provider": "vllm",
        "available": vllm_models is not None,
        "reason": None if vllm_models is not None else f"no vLLM server at {settings.vllm.base_url or '(unset)'}",
        "models": vllm_models or [],
    })
    return catalog
