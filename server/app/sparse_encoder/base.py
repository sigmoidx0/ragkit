from __future__ import annotations

from typing import NamedTuple, Protocol


class SparseVector(NamedTuple):
    indices: list[int]
    values: list[float]


class SparseEncoder(Protocol):
    def encode_documents(self, texts: list[str]) -> list[SparseVector]: ...
    def encode_query(self, text: str) -> SparseVector: ...
