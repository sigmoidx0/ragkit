"""Document sets: named groups of a workspace's documents that agents search."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.config import load_agent_config
from app.api.deps import DbDep, WorkspaceMemberDep, WorkspaceWriterDep
from app.db.models import Agent, Document, DocumentSet, DocumentSetDocument
from app.schemas.document_sets import AgentRef, DocumentSetCreate, DocumentSetOut, DocumentSetUpdate

router = APIRouter(tags=["document-sets"])


def _out(db: Session, ds: DocumentSet, agents: list[Agent]) -> DocumentSetOut:
    document_ids = list(
        db.execute(
            select(DocumentSetDocument.document_id).where(DocumentSetDocument.document_set_id == ds.id)
        ).scalars()
    )
    return DocumentSetOut(
        id=ds.id,
        workspace_id=ds.workspace_id,
        name=ds.name,
        description=ds.description,
        document_ids=sorted(document_ids),
        used_by=[AgentRef(id=a.id, name=a.name) for a in agents if ds.id in load_agent_config(a).document_set_ids],
        created_at=ds.created_at,
        updated_at=ds.updated_at,
    )


def _workspace_agents(db: Session, workspace_id: int) -> list[Agent]:
    return list(db.execute(select(Agent).where(Agent.workspace_id == workspace_id)).scalars())


def _get_set(db: Session, workspace_id: int, set_id: int) -> DocumentSet:
    ds = db.get(DocumentSet, set_id)
    if not ds or ds.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document set not found")
    return ds


def _set_documents(db: Session, ds: DocumentSet, document_ids: list[int]) -> None:
    wanted = set(document_ids)
    owned = set(
        db.execute(
            select(Document.id).where(Document.workspace_id == ds.workspace_id, Document.id.in_(wanted))
        ).scalars()
    )
    if missing := wanted - owned:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"documents not in this workspace: {sorted(missing)}")
    db.execute(delete(DocumentSetDocument).where(DocumentSetDocument.document_set_id == ds.id))
    db.add_all(DocumentSetDocument(document_set_id=ds.id, document_id=d) for d in sorted(wanted))


def _commit_unique(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "a document set with this name already exists") from exc


@router.get("/workspaces/{workspace_id}/document-sets", response_model=list[DocumentSetOut])
def list_document_sets(workspace_id: int, _membership: WorkspaceMemberDep, db: DbDep) -> list[DocumentSetOut]:
    agents = _workspace_agents(db, workspace_id)
    sets = db.execute(
        select(DocumentSet).where(DocumentSet.workspace_id == workspace_id).order_by(DocumentSet.name)
    ).scalars()
    return [_out(db, ds, agents) for ds in sets]


@router.post(
    "/workspaces/{workspace_id}/document-sets", response_model=DocumentSetOut, status_code=status.HTTP_201_CREATED
)
def create_document_set(
    workspace_id: int, body: DocumentSetCreate, _writer: WorkspaceWriterDep, db: DbDep
) -> DocumentSetOut:
    ds = DocumentSet(workspace_id=workspace_id, name=body.name.strip(), description=body.description)
    db.add(ds)
    db.flush()
    _set_documents(db, ds, body.document_ids)
    _commit_unique(db)
    db.refresh(ds)
    return _out(db, ds, _workspace_agents(db, workspace_id))


@router.patch("/workspaces/{workspace_id}/document-sets/{set_id}", response_model=DocumentSetOut)
def update_document_set(
    workspace_id: int, set_id: int, body: DocumentSetUpdate, _writer: WorkspaceWriterDep, db: DbDep
) -> DocumentSetOut:
    ds = _get_set(db, workspace_id, set_id)
    if body.name is not None:
        ds.name = body.name.strip()
    if body.description is not None:
        ds.description = body.description or None
    if body.document_ids is not None:
        _set_documents(db, ds, body.document_ids)
    _commit_unique(db)
    db.refresh(ds)
    return _out(db, ds, _workspace_agents(db, workspace_id))


@router.delete("/workspaces/{workspace_id}/document-sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_set(workspace_id: int, set_id: int, _writer: WorkspaceWriterDep, db: DbDep) -> None:
    ds = _get_set(db, workspace_id, set_id)
    # Refuse rather than quietly edit agents: an agent would silently lose
    # those documents from what it can answer from.
    users = [a.name for a in _workspace_agents(db, workspace_id) if set_id in load_agent_config(a).document_set_ids]
    if users:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"still used by agent(s): {', '.join(users)} — remove it from them first"
        )
    db.delete(ds)
    db.commit()
