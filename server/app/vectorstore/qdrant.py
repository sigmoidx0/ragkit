"""Qdrant vector store implementation."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.core.config import get_settings
from app.vectorstore.base import SearchHit, VectorStore

if TYPE_CHECKING:
    from fastembed import SparseTextEmbedding

logger = logging.getLogger(__name__)

_DENSE = "dense"
_SPARSE = "sparse"


class QdrantStore:
    """Dense-only vector store backed by Qdrant."""

    def __init__(
        self,
        url: str,
        collection: str,
        vector_size: int,
        distance: str = "Cosine",
        api_key: str | None = None,
    ) -> None:
        self._client = QdrantClient(url=url, api_key=api_key)
        self._collection = collection
        self._vector_size = vector_size
        self._distance = getattr(qm.Distance, distance.upper(), qm.Distance.COSINE)

    # ------------------------------------------------------------------
    # Hook methods — overridden by HybridQdrantStore
    # ------------------------------------------------------------------

    def _collection_config(self) -> dict[str, Any]:
        return {"vectors_config": qm.VectorParams(size=self._vector_size, distance=self._distance)}

    def _validate_existing(self) -> None:
        pass

    def _build_points(
        self,
        point_ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> list[qm.PointStruct]:
        return [
            qm.PointStruct(id=pid, vector=vec, payload=payload)
            for pid, vec, payload in zip(point_ids, vectors, payloads, strict=True)
        ]

    def _do_search(
        self,
        vector: list[float],
        top_k: int,
        flt: qm.Filter | None,
        query_text: str | None,
    ) -> list[SearchHit]:
        results = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            query_filter=flt,
            limit=top_k,
            with_payload=True,
        )
        return _to_hits(results.points)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def ensure_collection(self) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        if self._collection in existing:
            self._validate_existing()
            return

        logger.info("Creating Qdrant collection %s", self._collection)
        self._client.create_collection(collection_name=self._collection, **self._collection_config())
        for field in ("document_id", "service_id"):
            self._client.create_payload_index(
                collection_name=self._collection,
                field_name=field,
                field_schema=qm.PayloadSchemaType.INTEGER,
            )

    def upsert(
        self,
        *,
        point_ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        if not point_ids:
            return
        self._client.upsert(
            collection_name=self._collection,
            points=self._build_points(point_ids, vectors, payloads),
            wait=True,
        )

    def delete_document(self, document_id: int) -> None:
        self._client.delete(
            collection_name=self._collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id))]
                )
            ),
            wait=True,
        )

    def delete_points(self, point_ids: list[str]) -> None:
        if not point_ids:
            return
        self._client.delete(
            collection_name=self._collection,
            points_selector=qm.PointIdsList(points=point_ids),
            wait=True,
        )

    def search(
        self,
        *,
        vector: list[float],
        top_k: int,
        service_id: int | None = None,
        document_id: int | None = None,
        query_text: str | None = None,
    ) -> list[SearchHit]:
        conditions = []
        if service_id is not None:
            conditions.append(qm.FieldCondition(key="service_id", match=qm.MatchValue(value=service_id)))
        if document_id is not None:
            conditions.append(qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id)))
        flt = qm.Filter(must=conditions) if conditions else None
        return self._do_search(vector, top_k, flt, query_text)


class HybridQdrantStore(QdrantStore):
    """Dense + BM25 sparse hybrid store with RRF fusion."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        from fastembed import SparseTextEmbedding
        self._bm25: SparseTextEmbedding = SparseTextEmbedding(model_name="Qdrant/bm25")

    def _collection_config(self) -> dict[str, Any]:
        return {
            "vectors_config": {_DENSE: qm.VectorParams(size=self._vector_size, distance=self._distance)},
            "sparse_vectors_config": {_SPARSE: qm.SparseVectorParams()},
        }

    def _validate_existing(self) -> None:
        info = self._client.get_collection(self._collection)
        sparse_cfg = getattr(info.config.params, "sparse_vectors", None) or {}
        if _SPARSE not in sparse_cfg:
            raise RuntimeError(
                f"Collection '{self._collection}' exists but is not configured for hybrid search. "
                "Drop the collection and restart, or set search.hybrid=false in config.yaml."
            )

    def _build_points(
        self,
        point_ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> list[qm.PointStruct]:
        texts = [p.get("text", "") for p in payloads]
        sparse_results = list(self._bm25.embed(texts))
        return [
            qm.PointStruct(
                id=pid,
                vector={
                    _DENSE: vec,
                    _SPARSE: qm.SparseVector(
                        indices=sp.indices.tolist(),
                        values=sp.values.tolist(),
                    ),
                },
                payload=payload,
            )
            for pid, vec, payload, sp in zip(point_ids, vectors, payloads, sparse_results, strict=True)
        ]

    def _do_search(
        self,
        vector: list[float],
        top_k: int,
        flt: qm.Filter | None,
        query_text: str | None,
    ) -> list[SearchHit]:
        if not query_text:
            return super()._do_search(vector, top_k, flt, query_text)
        sparse_query = list(self._bm25.query_embed([query_text]))[0]
        results = self._client.query_points(
            collection_name=self._collection,
            prefetch=[
                qm.Prefetch(query=vector, using=_DENSE, limit=top_k * 2, filter=flt),
                qm.Prefetch(
                    query=qm.SparseVector(
                        indices=sparse_query.indices.tolist(),
                        values=sparse_query.values.tolist(),
                    ),
                    using=_SPARSE,
                    limit=top_k * 2,
                    filter=flt,
                ),
            ],
            query=qm.FusionQuery(fusion=qm.Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
        return _to_hits(results.points)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _to_hits(points: list[Any]) -> list[SearchHit]:
    return [
        SearchHit(point_id=str(r.id), score=float(r.score), payload=r.payload or {})
        for r in points
    ]

# singleton
@lru_cache(maxsize=1)
def get_vectorstore() -> VectorStore:
    cfg = get_settings().vectorstore
    kwargs = dict(
        url=cfg.url,
        collection=cfg.collection,
        vector_size=cfg.vector_size,
        distance=cfg.distance,
        api_key=cfg.api_key,
    )
    cls = HybridQdrantStore if get_settings().search.hybrid else QdrantStore
    return cls(**kwargs)


def reset_vectorstore_cache() -> None:
    get_vectorstore.cache_clear()
