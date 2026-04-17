"""Embedder protocol: both documents and query embeddings.

Matches the shape LangChain expects for `Embeddings`, so any of these classes
can also be passed directly where a LangChain embeddings object is required.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...
