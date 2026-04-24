"""Documents API: one file per document, replace supported."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DbDep, ServiceAdminDep, ServiceMemberDep, ServiceWriterDep
from app.db.models import Document, DocumentStatus, Service
from app.ingest.loaders import guess_mime_type, convert_to_documents
from app.schemas.documents import AnyChunkConfig, DocumentListResponse, DocumentOut
from app.services.documents import delete_document, delete_document_dir, save_document_file
from app.services.indexing import index_document, clear_document_index
from app.storage import get_storage

_chunk_config_adapter = TypeAdapter(AnyChunkConfig)

router = APIRouter(prefix="/services/{service_id}/documents", tags=["documents"])


def get_tx_db(db: DbDep) -> Iterator[Session]:
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


TxDbDep = Annotated[Session, Depends(get_tx_db)]


@router.get("", response_model=DocumentListResponse)
def list_documents(
    service_id: int,
    db: DbDep,
    _membership: ServiceMemberDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None),
) -> DocumentListResponse:
    stmt = select(Document).where(Document.service_id == service_id)
    count_stmt = select(func.count()).select_from(Document).where(Document.service_id == service_id)
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
    return DocumentListResponse(
        items=[DocumentOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    service_id: int,
    _writer: ServiceWriterDep,
    db: TxDbDep,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str | None = Form(None),
    chunk_config: str | None = Form(None),
) -> DocumentOut:
    if not db.get(Service, service_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "service not found")
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file is required")

    parsed_chunk_config = _parse_chunk_config(chunk_config)

    document = Document(
        service_id=service_id,
        title=title,
        description=description,
        source_filename=file.filename,
        mime_type=file.content_type or guess_mime_type(file.filename),
        file_path="",
        size_bytes=0,
        sha256="",
        status=DocumentStatus.pending,
        chunk_config=parsed_chunk_config,
    )
    db.add(document)
    db.flush()

    save_document_file(document, file.file, file.filename, file.content_type)
    db.flush()

    with get_storage().as_local_path(document.file_path) as path:
        docs = convert_to_documents(path)
    try:
        index_document(db, document, docs)
    except Exception as e:
        delete_document_dir(document.id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"indexing failed: {e}") from e
    return DocumentOut.model_validate(document)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(service_id: int, document_id: int, db: DbDep, _membership: ServiceMemberDep) -> DocumentOut:
    document = db.execute(
        select(Document).where(Document.id == document_id, Document.service_id == service_id)
    ).scalar_one_or_none()
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return DocumentOut.model_validate(document)


@router.post("/{document_id}/replace", response_model=DocumentOut)
def replace_document(
    service_id: int,
    document_id: int,
    _writer: ServiceWriterDep,
    db: TxDbDep,
    file: UploadFile = File(...),
    chunk_config: str | None = Form(None),
) -> DocumentOut:
    document = db.execute(
        select(Document).where(Document.id == document_id, Document.service_id == service_id)
    ).scalar_one_or_none()
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file is required")

    clear_document_index(document)
    delete_document_dir(document_id)

    parsed_chunk_config = _parse_chunk_config(chunk_config)
    save_document_file(document, file.file, file.filename, file.content_type)
    document.chunk_config = parsed_chunk_config
    document.status = DocumentStatus.pending
    document.error = None
    db.flush()

    with get_storage().as_local_path(document.file_path) as path:
        docs = convert_to_documents(path)
    index_document(db, document, docs)
    return DocumentOut.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_endpoint(
    service_id: int,
    document_id: int,
    _writer: ServiceWriterDep,
    db: TxDbDep,
) -> None:
    document = db.execute(
        select(Document).where(Document.id == document_id, Document.service_id == service_id)
    ).scalar_one_or_none()
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    delete_document(document)
    db.delete(document)


@router.get("/{document_id}/preview-text")
def preview_text(service_id: int, document_id: int, db: DbDep, _membership: ServiceMemberDep) -> dict[str, str]:
    document = db.execute(
        select(Document).where(Document.id == document_id, Document.service_id == service_id)
    ).scalar_one_or_none()
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    with get_storage().as_local_path(document.file_path) as path:
        try:
            docs = convert_to_documents(path)
        except Exception as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"conversion failed: {e}") from e
    return {"text": "\n\n".join(d.page_content for d in docs)}


@router.get("/{document_id}/file")
def download_file(
    service_id: int, document_id: int, db: DbDep, _membership: ServiceMemberDep
) -> Response:
    document = db.execute(
        select(Document).where(Document.id == document_id, Document.service_id == service_id)
    ).scalar_one_or_none()
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    storage = get_storage()
    try:
        abs_path = storage.absolute(document.file_path)
        if not abs_path.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing on disk")
        return FileResponse(str(abs_path), filename=document.source_filename)
    except NotImplementedError:
        pass
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    url = storage.presigned_url(document.file_path)
    if url:
        return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "file download not supported for this storage backend")


def _parse_chunk_config(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"chunk_config is not valid JSON: {e}") from e
    try:
        validated = _chunk_config_adapter.validate_python(data)
        return validated.model_dump(exclude_none=True)
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid chunk_config: {e}") from e
