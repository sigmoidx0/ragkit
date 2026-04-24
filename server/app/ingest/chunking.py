"""Text chunking: strategy implementations + config-driven factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from langchain_text_splitters import (
    CharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
)

from app.core.config import get_settings


@dataclass
class ChunkRecord:
    ordinal: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkStrategy(Protocol):
    def split(self, docs: list) -> list[ChunkRecord]: ...


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------

class RecursiveChunkStrategy:
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,
        )

    def split(self, docs: list) -> list[ChunkRecord]:
        return _records_from_docs(self._splitter.split_documents(docs))


class MarkdownHeaderChunkStrategy:
    """Split by Markdown headers (H1–H4), with an optional secondary size-based pass."""

    _HEADER_NAMES = {"#": "H1", "##": "H2", "###": "H3", "####": "H4"}

    def __init__(
        self,
        headers_to_split_on: list[str],
        chunk_size: int | None = None,
        chunk_overlap: int = 0,
    ) -> None:
        pairs = [(h, self._HEADER_NAMES.get(h, h.lstrip("#"))) for h in headers_to_split_on]
        self._header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=pairs)
        self._secondary: RecursiveCharacterTextSplitter | None = (
            RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                add_start_index=True,
            )
            if chunk_size
            else None
        )

    def split(self, docs: list) -> list[ChunkRecord]:
        full_text = "\n\n".join(d.page_content for d in docs)
        header_docs = self._header_splitter.split_text(full_text)
        if self._secondary:
            header_docs = self._secondary.split_documents(header_docs)
        return _records_from_docs(header_docs)


class CharacterChunkStrategy:
    def __init__(self, separator: str, chunk_size: int, chunk_overlap: int) -> None:
        self._splitter = CharacterTextSplitter(
            separator=separator,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,
        )

    def split(self, docs: list) -> list[ChunkRecord]:
        return _records_from_docs(self._splitter.split_documents(docs))


class TokenChunkStrategy:
    """Split by token count using tiktoken (default: cl100k_base / GPT-4 encoding)."""

    def __init__(
        self,
        chunk_size: int,
        chunk_overlap: int,
        encoding_name: str = "cl100k_base",
    ) -> None:
        self._splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            encoding_name=encoding_name,
        )

    def split(self, docs: list) -> list[ChunkRecord]:
        return _records_from_docs(self._splitter.split_documents(docs))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _records_from_docs(langchain_docs: list) -> list[ChunkRecord]:
    out: list[ChunkRecord] = []
    for i, d in enumerate(langchain_docs):
        text = d.page_content.strip()
        if text:
            out.append(ChunkRecord(ordinal=i, text=text, metadata=dict(d.metadata or {})))
    return out


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def default_chunk_strategy() -> ChunkStrategy:
    cfg = get_settings().ingest
    return RecursiveChunkStrategy(chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap)


def chunk_strategy_from_config(config: dict[str, Any] | None) -> ChunkStrategy:
    """Return a ChunkStrategy from a stored chunk_config dict (or None → global default)."""
    if config is None:
        return default_chunk_strategy()

    defaults = get_settings().ingest
    strategy = config.get("strategy", "recursive")

    if strategy == "recursive":
        return RecursiveChunkStrategy(
            chunk_size=config.get("chunk_size") or defaults.chunk_size,
            chunk_overlap=config.get("chunk_overlap") if config.get("chunk_overlap") is not None else defaults.chunk_overlap,
        )

    if strategy == "markdown_header":
        return MarkdownHeaderChunkStrategy(
            headers_to_split_on=config.get("headers_to_split_on") or ["#", "##", "###"],
            chunk_size=config.get("chunk_size"),
            chunk_overlap=config.get("chunk_overlap") or 0,
        )

    if strategy == "character":
        return CharacterChunkStrategy(
            separator=config.get("separator") or "\n\n",
            chunk_size=config.get("chunk_size") or defaults.chunk_size,
            chunk_overlap=config.get("chunk_overlap") if config.get("chunk_overlap") is not None else defaults.chunk_overlap,
        )

    if strategy == "token":
        return TokenChunkStrategy(
            chunk_size=config.get("chunk_size") or 512,
            chunk_overlap=config.get("chunk_overlap") or 50,
            encoding_name=config.get("encoding_name") or "cl100k_base",
        )

    raise ValueError(f"unknown chunking strategy: {strategy!r}")
