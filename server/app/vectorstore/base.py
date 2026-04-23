"""VectorStore protocol: backend-agnostic interface for vector operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class SearchHit:
    point_id: str
    score: float
    payload: dict[str, Any]


class VectorStore(Protocol):
    def ensure_collection(self) -> None: ...

    def upsert(
        self,
        *,
        point_ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None: ...

    def delete_document(self, document_id: int) -> None: ...

    def delete_points(self, point_ids: list[str]) -> None: ...

    def search(
        self,
        *,
        vector: list[float],
        top_k: int,
        service_id: int | None = None,
        document_id: int | None = None,
    ) -> list[SearchHit]: ...
