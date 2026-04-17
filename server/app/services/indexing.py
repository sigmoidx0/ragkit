"""Index one document file into Qdrant (no chunk rows in RDB)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import Document, DocumentStatus
from app.embeddings import get_embedder
from app.ingest import ingest_file
from app.storage import get_storage
from app.vectorstore import get_vectorstore

logger = logging.getLogger(__name__)


def index_document(db: Session, document: Document) -> None:
    """Run ingest + embedding + Qdrant upsert and update document status."""
    storage = get_storage()
    vs = get_vectorstore()
    embedder = get_embedder()
    vs.ensure_collection()

    abs_path: Path = storage.absolute(document.file_path)
    inserted_point_ids: list[str] = []
    try:
        chunks = ingest_file(abs_path)
        if not chunks:
            raise RuntimeError("no text extracted from file")

        texts = [c.text for c in chunks]
        vectors = embedder.embed_documents(texts)
        if len(vectors) != len(texts):
            raise RuntimeError("embedder returned wrong number of vectors")

        point_ids = [str(uuid.uuid4()) for _ in chunks]
        payloads = [
            {
                "document_id": document.id,
                "ordinal": c.ordinal,
                "text": c.text,
                "source_metadata": c.metadata,
            }
            for c in chunks
        ]

        vs.upsert(point_ids=point_ids, vectors=vectors, payloads=payloads)
        inserted_point_ids = point_ids
        document.status = DocumentStatus.ready
        document.error = None
    except Exception as e:
        logger.exception("indexing failed for document %s", document.id)
        if inserted_point_ids:
            try:
                vs.delete_points(inserted_point_ids)
            except Exception:
                logger.exception("qdrant cleanup failed for document %s", document.id)
        document.status = DocumentStatus.failed
        document.error = str(e)[:1000]

    db.flush()


def clear_document_index(document: Document) -> None:
    vs = get_vectorstore()
    try:
        vs.delete_document(document.id)
    except Exception:
        logger.exception("qdrant delete failed for document %s", document.id)


def delete_document(document: Document) -> None:
    clear_document_index(document)
    get_storage().delete_document_dir(document.id)
