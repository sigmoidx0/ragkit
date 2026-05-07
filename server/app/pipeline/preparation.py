"""Pre-flight model readiness checks and eager loading for pipeline execution."""

from __future__ import annotations

from typing import Any


def check_readiness(graph_json: dict[str, Any]) -> dict[str, Any]:
    """Return which components are already loaded vs. need initialization.

    Each component maps to True (warm/cached) or False (cold, will load on first use).
    """
    node_types = {n["type"] for n in graph_json["nodes"]}
    components: dict[str, bool] = {}

    if "EmbedNode" in node_types:
        from app.embeddings import get_embedder
        components["embedder"] = get_embedder.cache_info().currsize > 0

    if "RerankNode" in node_types:
        from app.rag.reranker import get_reranker
        components["reranker"] = get_reranker.cache_info().currsize > 0

    return {
        "ready": all(components.values()),
        "components": components,
    }


def prepare_pipeline(graph_json: dict[str, Any]) -> None:
    """Eagerly initialize all models required by the pipeline.

    Blocks until every cold component is loaded. Safe to call when already warm
    (lru_cache makes subsequent calls free).
    """
    node_types = {n["type"] for n in graph_json["nodes"]}

    if "EmbedNode" in node_types:
        from app.embeddings import get_embedder
        get_embedder()

    if "RerankNode" in node_types:
        from app.rag.reranker import get_reranker
        get_reranker()
