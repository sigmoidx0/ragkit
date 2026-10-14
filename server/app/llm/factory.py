"""Construct chat models from an LLM config.

`config.yaml` supplies the default, but any caller can pass its own `LlmSection`
instead — that is how one agent runs on Ollama while another runs on Gemini.
Models are cached per distinct config rather than globally, so switching
providers per agent costs nothing after the first build.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.core.config import LlmSection, get_settings

# Keyed by the settings that actually change the client, so two agents sharing a
# provider and model share one instance.
_cache: dict[tuple, BaseChatModel] = {}


def _cache_key(cfg: LlmSection) -> tuple:
    return (
        cfg.provider,
        cfg.model,
        cfg.temperature,
        cfg.max_tokens,
        cfg.api_key,
        cfg.ollama.base_url,
        cfg.vllm.base_url,
        cfg.google.base_url,
    )


def _build_chat_model(cfg: LlmSection) -> BaseChatModel:
    kwargs: dict = {"temperature": cfg.temperature}

    if cfg.provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=cfg.model,
            base_url=cfg.ollama.base_url,
            num_predict=cfg.max_tokens,
            **kwargs,
        )
    if cfg.provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            max_tokens=cfg.max_tokens,
            **kwargs,
        )
    if cfg.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=cfg.model,
            api_key=cfg.api_key,
            max_tokens=cfg.max_tokens,
            **kwargs,
        )
    if cfg.provider == "google":
        # Gemini rides its OpenAI-compatible endpoint — see app/llm/gemini.py.
        from app.llm.gemini import ChatGemini
        return ChatGemini(
            model=cfg.model,
            base_url=cfg.google.base_url,
            api_key=cfg.api_key,
            max_tokens=cfg.max_tokens,
            **kwargs,
        )
    if cfg.provider == "vllm":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=cfg.model,
            base_url=cfg.vllm.base_url,
            api_key="dummy",
            max_tokens=cfg.max_tokens,
            **kwargs,
        )
    raise ValueError(f"unsupported LLM provider: {cfg.provider}")


def get_chat_model(llm_cfg: LlmSection | None = None) -> BaseChatModel:
    """Return the chat model for `llm_cfg`, defaulting to the one in config.yaml."""
    cfg = llm_cfg or get_settings().llm
    key = _cache_key(cfg)
    if key not in _cache:
        _cache[key] = _build_chat_model(cfg)
    return _cache[key]


def reset_chat_model_cache() -> None:
    _cache.clear()
