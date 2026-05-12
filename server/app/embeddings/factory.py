"""Construct the embedder selected by `config.yaml` or per-node config override."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.embeddings.azure_openai import AzureOpenAIEmbedder
from app.embeddings.base import Embedder
from app.embeddings.ollama import OllamaEmbedder
from app.embeddings.tei import TeiEmbedder
from app.embeddings.vllm import VllmEmbedder


@lru_cache(maxsize=8)
def _build_embedder(provider: str, model: str | None) -> Embedder:
    cfg = get_settings().embeddings
    if provider == "ollama":
        return OllamaEmbedder(base_url=cfg.ollama.base_url, model=model or cfg.ollama.model)
    if provider == "tei":
        return TeiEmbedder(base_url=cfg.tei.base_url, api_key=cfg.api_key)
    if provider == "vllm":
        return VllmEmbedder(
            base_url=cfg.vllm.base_url,
            model=model or cfg.vllm.model,
            api_key=cfg.api_key,
        )
    if provider == "azure_openai":
        return AzureOpenAIEmbedder(
            endpoint=cfg.azure_openai.endpoint,
            deployment=model or cfg.azure_openai.deployment,
            api_version=cfg.azure_openai.api_version,
            api_key=cfg.api_key,
        )
    raise ValueError(f"unsupported embeddings provider: {provider}")


def get_embedder(provider: str | None = None, model: str | None = None) -> Embedder:
    """Return an embedder, using global config as defaults for unspecified params."""
    cfg = get_settings().embeddings
    return _build_embedder(provider or cfg.provider, model or None)


def reset_embedder_cache() -> None:
    _build_embedder.cache_clear()
