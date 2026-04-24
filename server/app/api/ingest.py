"""Ingest utilities: preview chunking without persisting to DB."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import TypeAdapter, ValidationError

from app.api.deps import CurrentUser
from app.ingest.chunking import chunk_strategy_from_config
from app.ingest.loaders import convert_to_documents
from app.schemas.documents import AnyChunkConfig, ChunkPreviewChunk, ChunkPreviewResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])

_chunk_config_adapter = TypeAdapter(AnyChunkConfig)
_MARKDOWN_LIMIT = 50_000


@router.post("/preview-chunks", response_model=ChunkPreviewResponse)
def preview_chunks(
    _user: CurrentUser,
    file: UploadFile = File(...),
    chunk_config: str | None = Form(None),
) -> ChunkPreviewResponse:
    """Convert a file to markdown and apply a chunking strategy — no DB writes."""
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file is required")

    cfg: dict | None = None
    if chunk_config:
        try:
            data = json.loads(chunk_config)
        except json.JSONDecodeError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"chunk_config is not valid JSON: {e}") from e
        try:
            validated = _chunk_config_adapter.validate_python(data)
            cfg = validated.model_dump(exclude_none=True)
        except ValidationError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid chunk_config: {e}") from e

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        docs = convert_to_documents(tmp_path)
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"conversion failed: {e}") from e
    finally:
        tmp_path.unlink(missing_ok=True)

    markdown = "\n\n".join(d.page_content for d in docs)
    truncated = len(markdown) > _MARKDOWN_LIMIT
    preview_markdown = markdown[:_MARKDOWN_LIMIT] if truncated else markdown

    try:
        strategy = chunk_strategy_from_config(cfg)
        chunks = strategy.split(docs)
    except Exception as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"chunking failed: {e}") from e

    return ChunkPreviewResponse(
        markdown=preview_markdown,
        markdown_truncated=truncated,
        chunks=[
            ChunkPreviewChunk(
                ordinal=c.ordinal,
                text=c.text,
                char_count=len(c.text),
                metadata=c.metadata,
            )
            for c in chunks
        ],
        total_chunks=len(chunks),
    )
