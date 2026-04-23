"""Qdrant vector store implementation."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.core.config import get_settings
from app.vectorstore.base import SearchHit, VectorStore

logger = logging.getLogger(__name__)


class QdrantStore:
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

    def ensure_collection(self) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        if self._collection in existing:
            return
        logger.info("Creating Qdrant collection %s", self._collection)
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=qm.VectorParams(size=self._vector_size, distance=self._distance),
        )
        self._client.create_payload_index(
            collection_name=self._collection,
            field_name="document_id",
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
        points = [
            qm.PointStruct(id=pid, vector=vec, payload=payload)
            for pid, vec, payload in zip(point_ids, vectors, payloads, strict=True)
        ]
        self._client.upsert(collection_name=self._collection, points=points, wait=True)

    def delete_document(self, document_id: int) -> None:
        self._client.delete(
            collection_name=self._collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="document_id", match=qm.MatchValue(value=document_id)
                        )
                    ]
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
    ) -> list[SearchHit]:
        conditions = []
        if service_id is not None:
            conditions.append(qm.FieldCondition(key="service_id", match=qm.MatchValue(value=service_id)))
        if document_id is not None:
            conditions.append(qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id)))
        flt = qm.Filter(must=conditions) if conditions else None
        results = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            query_filter=flt,
            limit=top_k,
            with_payload=True,
        )
        return [
            SearchHit(point_id=str(r.id), score=float(r.score), payload=r.payload or {})
            for r in results.points
        ]


@lru_cache(maxsize=1)
def get_vectorstore() -> VectorStore:
    cfg = get_settings().vectorstore
    return QdrantStore(
        url=cfg.url,
        collection=cfg.collection,
        vector_size=cfg.vector_size,
        distance=cfg.distance,
        api_key=cfg.api_key,
    )


def reset_vectorstore_cache() -> None:
    get_vectorstore.cache_clear()
