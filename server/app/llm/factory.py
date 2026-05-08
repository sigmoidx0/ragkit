"""Construct the chat model selected by `config.yaml`."""

from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    cfg = get_settings().llm
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


def reset_chat_model_cache() -> None:
    get_chat_model.cache_clear()
