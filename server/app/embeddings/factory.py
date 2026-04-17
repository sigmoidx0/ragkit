"""Construct the embedder selected by `config.yaml`."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.embeddings.azure_openai import AzureOpenAIEmbedder
from app.embeddings.base import Embedder
from app.embeddings.ollama import OllamaEmbedder
from app.embeddings.tei import TeiEmbedder
from app.embeddings.vllm import VllmEmbedder


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    cfg = get_settings().embeddings
    provider = cfg.provider

    if provider == "ollama":
        return OllamaEmbedder(base_url=cfg.ollama.base_url, model=cfg.ollama.model)
    if provider == "tei":
        return TeiEmbedder(base_url=cfg.tei.base_url, api_key=cfg.api_key)
    if provider == "vllm":
        return VllmEmbedder(
            base_url=cfg.vllm.base_url, model=cfg.vllm.model, api_key=cfg.api_key
        )
    if provider == "azure_openai":
        return AzureOpenAIEmbedder(
            endpoint=cfg.azure_openai.endpoint,
            deployment=cfg.azure_openai.deployment,
            api_version=cfg.azure_openai.api_version,
            api_key=cfg.api_key,
        )
    raise ValueError(f"unsupported embeddings provider: {provider}")


def reset_embedder_cache() -> None:
    get_embedder.cache_clear()
