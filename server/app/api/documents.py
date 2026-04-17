"""Documents API: one file per document, replace supported."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbDep
from app.db.models import Document, DocumentStatus
from app.ingest.loaders import guess_mime_type
from app.mappers.document_mapper import to_document_list_response, to_document_out
from app.schemas.documents import DocumentListResponse, DocumentOut
from app.services.indexing import clear_document_index, delete_document, index_document
from app.storage import get_storage

router = APIRouter(prefix="/documents", tags=["documents"])


def get_tx_db(db: DbDep) -> Iterator[Session]:
    """Write transaction boundary to avoid scattered commit/rollback calls."""
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


TxDbDep = Annotated[Session, Depends(get_tx_db)]


@router.get("", response_model=DocumentListResponse)
def list_documents(
    db: DbDep,
    _user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None),
) -> DocumentListResponse:
    stmt = select(Document)
    count_stmt = select(func.count()).select_from(Document)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Document.title.ilike(like))
        count_stmt = count_stmt.where(Document.title.ilike(like))

    total = int(db.execute(count_stmt).scalar_one())
    rows = list(
        db.execute(stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return to_document_list_response(rows, total=total, limit=limit, offset=offset)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    _user: CurrentUser,
    db: TxDbDep,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str | None = Form(None),
) -> DocumentOut:
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file is required")

    mime = file.content_type or guess_mime_type(file.filename)
    document = Document(
        title=title,
        description=description,
        source_filename=file.filename,
        mime_type=mime,
        file_path="",
        size_bytes=0,
        sha256="",
        status=DocumentStatus.pending,
    )
    db.add(document)
    db.flush()

    storage = get_storage()
    stored = storage.save_document_file(
        document_id=document.id,
        original_filename=file.filename,
        source=file.file,
    )
    document.file_path = stored.relative_path
    document.size_bytes = stored.size_bytes
    document.sha256 = stored.sha256
    index_document(db, document)
    db.flush()
    return to_document_out(document)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: DbDep, _user: CurrentUser) -> DocumentOut:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return to_document_out(document)


@router.post("/{document_id}/replace", response_model=DocumentOut)
def replace_document(
    document_id: int,
    _user: CurrentUser,
    db: TxDbDep,
    file: UploadFile = File(...),
) -> DocumentOut:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file is required")

    storage = get_storage()
    clear_document_index(document)
    storage.delete_document_dir(document_id)

    stored = storage.save_document_file(
        document_id=document.id,
        original_filename=file.filename,
        source=file.file,
    )
    document.source_filename = file.filename
    document.mime_type = file.content_type or guess_mime_type(file.filename)
    document.file_path = stored.relative_path
    document.size_bytes = stored.size_bytes
    document.sha256 = stored.sha256
    document.status = DocumentStatus.pending
    document.error = None
    index_document(db, document)
    db.flush()
    return to_document_out(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_endpoint(
    document_id: int,
    _user: CurrentUser,
    db: TxDbDep,
) -> None:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    delete_document(document)
    db.delete(document)


@router.get("/{document_id}/file")
def download_file(document_id: int, db: DbDep, _user: CurrentUser) -> FileResponse:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    storage = get_storage()
    try:
        abs_path = storage.absolute(document.file_path)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    if not abs_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing on disk")
    return FileResponse(str(abs_path), filename=document.source_filename)
