"""File -> Documents -> chunks -> (text, metadata) records."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.ingest.loaders import load_file


@dataclass
class ChunkRecord:
    ordinal: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _rough_token_count(text: str) -> int:
    # Cheap heuristic: roughly 4 chars per token for English-ish text.
    return max(1, len(text) // 4)


def chunk_documents(
    docs: list, *, chunk_size: int, chunk_overlap: int
) -> list[ChunkRecord]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    split_docs = splitter.split_documents(docs)
    out: list[ChunkRecord] = []
    for i, d in enumerate(split_docs):
        text = d.page_content.strip()
        if not text:
            continue
        out.append(
            ChunkRecord(
                ordinal=i,
                text=text,
                metadata=dict(d.metadata or {}),
            )
        )
    return out


def ingest_file(path: Path) -> list[ChunkRecord]:
    cfg = get_settings().ingest
    docs = load_file(path)
    return chunk_documents(
        docs, chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap
    )
