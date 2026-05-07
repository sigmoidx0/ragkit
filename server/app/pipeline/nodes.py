"""Concrete node executor implementations for the search pipeline."""

from __future__ import annotations

import time
from typing import Any

from app.pipeline.registry import register
from app.pipeline.types import ExecutionContext, HandleDef, NodeDescriptor


class _QueryInputExecutor:
    descriptor = NodeDescriptor(
        node_type="QueryInput",
        label="Query Input",
        description="Pipeline entry point. Provides the user query and top_k to downstream nodes.",
        inputs=[],
        outputs=[HandleDef("query", "query")],
        config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )

    def execute(self, config: dict[str, Any], inputs: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        return {"query": ctx.run_inputs["query"]}


class _EmbedNodeExecutor:
    descriptor = NodeDescriptor(
        node_type="EmbedNode",
        label="Embed",
        description="Converts the query text into a vector using the configured embedding model.",
        inputs=[HandleDef("query", "query")],
        outputs=[HandleDef("vector", "vector")],
        config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )

    def execute(self, config: dict[str, Any], inputs: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        from app.embeddings import get_embedder
        vector = get_embedder().embed_query(inputs["query"])
        return {"vector": vector}


class _RetrieveNodeExecutor:
    descriptor = NodeDescriptor(
        node_type="RetrieveNode",
        label="Retrieve",
        description="Searches the vector store for chunks similar to the query.",
        inputs=[HandleDef("vector", "vector"), HandleDef("query", "query")],
        outputs=[HandleDef("hits", "hits")],
        config_schema={
            "type": "object",
            "properties": {
                "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 200},
                "document_id": {"type": ["integer", "null"], "default": None},
            },
            "additionalProperties": False,
        },
    )

    def execute(self, config: dict[str, Any], inputs: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        from app.core.config import get_settings
        from app.vectorstore import get_vectorstore

        settings = get_settings()
        top_k = int(config.get("top_k") or ctx.run_inputs.get("top_k") or settings.search.default_top_k)
        reranker_cfg = settings.search.reranker
        fetch_k = top_k * reranker_cfg.fetch_k_multiplier if reranker_cfg is not None else top_k

        hits = get_vectorstore().search(
            vector=inputs["vector"],
            top_k=fetch_k,
            service_id=ctx.service_id,
            document_id=config.get("document_id"),
            query_text=inputs["query"],
        )
        return {"hits": hits}


class _RerankNodeExecutor:
    descriptor = NodeDescriptor(
        node_type="RerankNode",
        label="Rerank",
        description="Reorders search hits by relevance using the configured reranker.",
        inputs=[HandleDef("hits", "hits"), HandleDef("query", "query")],
        outputs=[HandleDef("hits", "hits")],
        config_schema={
            "type": "object",
            "properties": {
                "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 200},
            },
            "additionalProperties": False,
        },
    )

    def execute(self, config: dict[str, Any], inputs: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        from app.core.config import get_settings
        from app.rag.reranker import get_reranker

        settings = get_settings()
        top_k = int(config.get("top_k") or ctx.run_inputs.get("top_k") or settings.search.default_top_k)
        reranked = get_reranker().rerank(inputs["query"], inputs["hits"], top_k)
        return {"hits": reranked}


class _EnrichNodeExecutor:
    descriptor = NodeDescriptor(
        node_type="EnrichNode",
        label="Enrich",
        description="Adds document metadata (title, ordinal) to search hits from the database.",
        inputs=[HandleDef("hits", "hits")],
        outputs=[HandleDef("results", "results")],
        config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )

    def execute(self, config: dict[str, Any], inputs: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        from app.rag.enrich import enrich_hits
        results = enrich_hits(ctx.db, inputs["hits"])
        return {"results": results}


class _OutputNodeExecutor:
    descriptor = NodeDescriptor(
        node_type="OutputNode",
        label="Output",
        description="Terminal node. Collects pipeline results for the response.",
        inputs=[HandleDef("results", "results")],
        outputs=[],
        config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )

    def execute(self, config: dict[str, Any], inputs: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        return {"results": inputs["results"]}


# Register all executors
register(_QueryInputExecutor())
register(_EmbedNodeExecutor())
register(_RetrieveNodeExecutor())
register(_RerankNodeExecutor())
register(_EnrichNodeExecutor())
register(_OutputNodeExecutor())
