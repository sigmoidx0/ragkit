from __future__ import annotations

from app.db.models import Document
from app.schemas.documents import DocumentListResponse, DocumentOut


def to_document_out(document: Document) -> DocumentOut:
    return DocumentOut.model_validate(document)


def to_document_list_response(
    documents: list[Document], *, total: int, limit: int, offset: int
) -> DocumentListResponse:
    return DocumentListResponse(
        items=[to_document_out(d) for d in documents],
        total=total,
        limit=limit,
        offset=offset,
    )
