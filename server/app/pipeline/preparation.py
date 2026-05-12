"""Pre-flight model readiness checks and eager loading for pipeline execution."""

from __future__ import annotations

from typing import Any


def _embed_node_config(graph_json: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract provider/model from the first EmbedNode in the graph, if any."""
    for node in graph_json["nodes"]:
        if node["type"] == "EmbedNode":
            cfg = node.get("data", {}).get("config", {})
            return cfg.get("provider") or None, cfg.get("model") or None
    return None, None


def _rerank_node_config(graph_json: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract provider/model from the first RerankNode in the graph, if any."""
    for node in graph_json["nodes"]:
        if node["type"] == "RerankNode":
            cfg = node.get("data", {}).get("config", {})
            return cfg.get("provider") or None, cfg.get("model") or None
    return None, None


def check_readiness(graph_json: dict[str, Any]) -> dict[str, Any]:
    """Return which components are already loaded vs. need initialization."""
    from app.embeddings.factory import _build_embedder
    from app.rag.reranker import _build_reranker

    node_types = {n["type"] for n in graph_json["nodes"]}
    components: dict[str, bool] = {}

    if "EmbedNode" in node_types:
        components["embedder"] = _build_embedder.cache_info().currsize > 0

    if "RerankNode" in node_types:
        components["reranker"] = _build_reranker.cache_info().currsize > 0

    return {
        "ready": all(components.values()),
        "components": components,
    }


def prepare_pipeline(graph_json: dict[str, Any]) -> None:
    """Eagerly initialize all models required by the pipeline."""
    node_types = {n["type"] for n in graph_json["nodes"]}

    if "EmbedNode" in node_types:
        from app.embeddings import get_embedder
        provider, model = _embed_node_config(graph_json)
        get_embedder(provider=provider, model=model)

    if "RerankNode" in node_types:
        from app.rag.reranker import get_reranker
        provider, model = _rerank_node_config(graph_json)
        get_reranker(provider=provider, model=model)
