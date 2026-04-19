"""Document file lifecycle: save, delete."""

from __future__ import annotations

from typing import BinaryIO

from app.db.models import Document
from app.ingest.loaders import guess_mime_type
from app.services.indexing import clear_document_index
from app.storage import get_storage


def save_document_file(
    document: Document,
    source: BinaryIO,
    filename: str,
    content_type: str | None,
) -> None:
    """Save uploaded file to storage and update document file fields."""
    storage = get_storage()
    stored = storage.save_document_file(
        document_id=document.id,
        original_filename=filename,
        source=source,
    )
    document.source_filename = filename
    document.mime_type = content_type or guess_mime_type(filename)
    document.file_path = stored.stored_path
    document.size_bytes = stored.size_bytes
    document.sha256 = stored.sha256


def delete_document(document: Document) -> None:
    clear_document_index(document)
    get_storage().delete_document_dir(document.id)


def delete_document_dir(document_id: int) -> None:
    get_storage().delete_document_dir(document_id)
