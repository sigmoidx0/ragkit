"""Text chunking: strategy interface + default recursive implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings


@dataclass
class ChunkRecord:
    ordinal: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkStrategy(Protocol):
    def split(self, docs: list) -> list[ChunkRecord]: ...


class RecursiveChunkStrategy:
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,
        )

    def split(self, docs: list) -> list[ChunkRecord]:
        out: list[ChunkRecord] = []
        for i, d in enumerate(self._splitter.split_documents(docs)):
            text = d.page_content.strip()
            if not text:
                continue
            out.append(ChunkRecord(ordinal=i, text=text, metadata=dict(d.metadata or {})))
        return out


def default_chunk_strategy() -> ChunkStrategy:
    cfg = get_settings().ingest
    return RecursiveChunkStrategy(chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap)
