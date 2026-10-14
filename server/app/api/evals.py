"""Evaluations: run a question set against an agent config and compare runs."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.agent.config import load_agent_config, resolve_llm
from app.api.deps import DbDep, ServiceAdminDep
from app.core.config import get_settings
from app.db.models import Document, EvalRun, Service, SystemPrompt
from app.eval.runner import execute_eval_run
from app.schemas.evals import EvalCreate, EvalRunOut

router = APIRouter(tags=["evals"])


def _get_run(db, service_id: int, run_id: int) -> EvalRun:
    run = db.get(EvalRun, run_id)
    if not run or run.service_id != service_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "evaluation not found")
    return run


@router.get("/services/{service_id}/evals", response_model=list[EvalRunOut])
def list_evals(service_id: int, _admin: ServiceAdminDep, db: DbDep) -> list[EvalRun]:
    return list(
        db.execute(
            select(EvalRun).where(EvalRun.service_id == service_id).order_by(EvalRun.created_at.desc())
        ).scalars()
    )


@router.post("/services/{service_id}/evals", response_model=EvalRunOut, status_code=status.HTTP_201_CREATED)
def create_eval(
    service_id: int,
    body: EvalCreate,
    background: BackgroundTasks,
    admin: ServiceAdminDep,
    db: DbDep,
) -> EvalRun:
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent not found")

    config = body.config or load_agent_config(service)
    try:
        resolve_llm(config)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    expected = {c.expected_document_id for c in body.cases if c.expected_document_id is not None}
    if expected:
        owned = set(
            db.execute(
                select(Document.id).where(Document.service_id == service_id, Document.id.in_(expected))
            ).scalars()
        )
        if missing := expected - owned:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"documents not in this agent: {sorted(missing)}")

    if body.system_prompt_id is not None:
        prompt = db.get(SystemPrompt, body.system_prompt_id)
        if not prompt or prompt.service_id != service_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "system prompt not in this agent")
    else:
        prompt = db.execute(
            select(SystemPrompt).where(SystemPrompt.service_id == service_id, SystemPrompt.is_active.is_(True))
        ).scalar_one_or_none()
    prompt_name = prompt.name if prompt else "fallback (config.yaml)"
    prompt_text = prompt.content if prompt else get_settings().chat.fallback_system_prompt

    run = EvalRun(
        service_id=service_id,
        name=body.name,
        prompt_name=prompt_name,
        system_prompt=prompt_text,
        status="pending",
        config_snapshot=config.model_dump(mode="json"),
        cases=[c.model_dump(mode="json") for c in body.cases],
        results=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    # Runs after the response, in this event loop; the UI polls for progress.
    background.add_task(execute_eval_run, run.id, admin.user_id)
    return run


@router.get("/services/{service_id}/evals/{run_id}", response_model=EvalRunOut)
def get_eval(service_id: int, run_id: int, _admin: ServiceAdminDep, db: DbDep) -> EvalRun:
    return _get_run(db, service_id, run_id)


@router.delete("/services/{service_id}/evals/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_eval(service_id: int, run_id: int, _admin: ServiceAdminDep, db: DbDep) -> None:
    run = _get_run(db, service_id, run_id)
    if run.status in ("pending", "running"):
        raise HTTPException(status.HTTP_409_CONFLICT, "evaluation is still running")
    db.delete(run)
    db.commit()
