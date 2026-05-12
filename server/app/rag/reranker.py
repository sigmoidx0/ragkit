"""Reranker implementations: reorder SearchHits by relevance to the query."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

from app.core.config import get_settings
from app.vectorstore import SearchHit

if TYPE_CHECKING:
    pass


class Reranker(Protocol):
    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]: ...


class _PassthroughReranker:
    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        return hits[:top_k]


class _CohereReranker:
    def __init__(self, model: str, api_key: str) -> None:
        import cohere  # pip install cohere

        self._client = cohere.Client(api_key=api_key)
        self._model = model

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        if not hits:
            return []
        docs = [str(h.payload.get("text", "")) for h in hits]
        response = self._client.rerank(
            model=self._model,
            query=query,
            documents=docs,
            top_n=top_k,
        )
        return [
            SearchHit(
                point_id=hits[r.index].point_id,
                score=r.relevance_score,
                payload=hits[r.index].payload,
            )
            for r in response.results
        ]


class _CrossEncoderReranker:
    def __init__(self, model: str) -> None:
        from sentence_transformers import CrossEncoder  # pip install sentence-transformers

        self._model = CrossEncoder(model)

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        if not hits:
            return []
        pairs = [[query, str(h.payload.get("text", ""))] for h in hits]
        scores: list[float] = self._model.predict(pairs).tolist()
        ranked = sorted(zip(scores, hits), key=lambda x: x[0], reverse=True)
        return [
            SearchHit(point_id=h.point_id, score=float(s), payload=h.payload)
            for s, h in ranked[:top_k]
        ]


@lru_cache(maxsize=4)
def _build_reranker(provider: str, model: str | None) -> Reranker:
    cfg = get_settings().search.reranker
    if provider == "passthrough":
        return _PassthroughReranker()
    if provider == "cohere":
        api_key = cfg.api_key if cfg else None
        if not api_key:
            raise ValueError("search.reranker.api_key (or RERANKER_API_KEY) is required for Cohere")
        return _CohereReranker(
            model=model or (cfg.model if cfg else "rerank-v3.5"),
            api_key=api_key,
        )
    if provider == "cross_encoder":
        return _CrossEncoderReranker(model=model or (cfg.model if cfg else "BAAI/bge-reranker-base"))
    raise ValueError(f"Unknown reranker provider: {provider!r}")


def get_reranker(provider: str | None = None, model: str | None = None) -> Reranker:
    """Return a reranker, using global config as defaults for unspecified params."""
    cfg = get_settings().search.reranker
    if provider is None:
        if cfg is None:
            return _build_reranker("passthrough", None)
        return _build_reranker(cfg.provider, model or cfg.model)
    return _build_reranker(provider, model or None)
