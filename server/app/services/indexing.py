"""Chunk, embed, and upsert a document into Qdrant."""

from __future__ import annotations

import logging
import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document, DocumentStatus
from app.embeddings import get_embedder
from app.ingest import chunk_strategy_from_config
from app.vectorstore import get_vectorstore

logger = logging.getLogger(__name__)


def _embedding_model_name() -> str:
    cfg = get_settings().embeddings
    if cfg.provider == "ollama":
        return f"ollama/{cfg.ollama.model}"
    if cfg.provider == "tei":
        return "tei"
    if cfg.provider == "vllm":
        return f"vllm/{cfg.vllm.model}"
    if cfg.provider == "azure_openai":
        return f"azure_openai/{cfg.azure_openai.deployment}"
    return cfg.provider


def _friendly_error(stage: DocumentStatus, exc: BaseException) -> str:
    if isinstance(exc, httpx.ConnectError):
        if stage == DocumentStatus.embedding:
            return "Embedding service (Ollama) is not reachable. Make sure Ollama is running."
        return "Vector store (Qdrant) is not reachable."
    return str(exc)


def index_document(db: Session, document: Document, docs: list) -> None:
    """Chunk, embed, upsert to Qdrant and update document status."""
    vs = get_vectorstore()
    embedder = get_embedder()
    vs.ensure_collection()

    inserted_point_ids: list[str] = []
    try:
        document.status = DocumentStatus.chunking
        db.flush()
        chunks = chunk_strategy_from_config(document.chunk_config).split(docs)
        if not chunks:
            raise RuntimeError("no text extracted from file")

        document.status = DocumentStatus.embedding
        db.flush()
        texts = [c.text for c in chunks]
        vectors = embedder.embed_documents(texts)
        if len(vectors) != len(texts):
            raise RuntimeError("embedder returned wrong number of vectors")

        point_ids = [str(uuid.uuid4()) for _ in chunks]
        payloads = [
            {
                "document_id": document.id,
                "service_id": document.service_id,
                "ordinal": c.ordinal,
                "text": c.text,
                "source_metadata": c.metadata,
            }
            for c in chunks
        ]

        vs.upsert(point_ids=point_ids, vectors=vectors, payloads=payloads)
        inserted_point_ids = point_ids
        document.status = DocumentStatus.indexed
        document.embedding_model = _embedding_model_name()
        document.error = None
    except Exception as e:
        logger.exception("indexing failed for document %s at stage %s", document.id, document.status)
        if inserted_point_ids:
            try:
                vs.delete_points(inserted_point_ids)
            except Exception:
                logger.exception("qdrant cleanup failed for document %s", document.id)
        raise RuntimeError(_friendly_error(document.status, e)) from e

    db.flush()


def clear_document_index(document: Document) -> None:
    vs = get_vectorstore()
    try:
        vs.delete_document(document.id)
    except Exception:
        logger.exception("qdrant delete failed for document %s", document.id)
