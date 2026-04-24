from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import DocumentStatus


# ---------------------------------------------------------------------------
# Chunk config schemas (discriminated union on `strategy`)
# ---------------------------------------------------------------------------

class RecursiveChunkConfig(BaseModel):
    strategy: Literal["recursive"] = "recursive"
    chunk_size: int | None = None
    chunk_overlap: int | None = None


class MarkdownHeaderChunkConfig(BaseModel):
    strategy: Literal["markdown_header"]
    headers_to_split_on: list[str] = Field(default_factory=lambda: ["#", "##", "###"])
    chunk_size: int | None = None
    chunk_overlap: int | None = None


class CharacterChunkConfig(BaseModel):
    strategy: Literal["character"]
    separator: str = "\n\n"
    chunk_size: int | None = None
    chunk_overlap: int | None = None


class TokenChunkConfig(BaseModel):
    strategy: Literal["token"]
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    encoding_name: str = "cl100k_base"


AnyChunkConfig = Annotated[
    Union[RecursiveChunkConfig, MarkdownHeaderChunkConfig, CharacterChunkConfig, TokenChunkConfig],
    Field(discriminator="strategy"),
]


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    title: str
    description: str | None
    source_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: DocumentStatus
    error: str | None
    chunk_config: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentOut]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Preview response
# ---------------------------------------------------------------------------

class ChunkPreviewChunk(BaseModel):
    ordinal: int
    text: str
    char_count: int
    metadata: dict[str, Any]


class ChunkPreviewResponse(BaseModel):
    markdown: str
    markdown_truncated: bool
    chunks: list[ChunkPreviewChunk]
    total_chunks: int
