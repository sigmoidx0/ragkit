"""Evaluations: run a question set against an agent config and compare runs."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.agent.config import load_agent_config, resolve_llm
from app.api.deps import AgentAdminDep, DbDep
from app.core.config import get_settings
from app.db.models import Document, EvalRun, SystemPrompt
from app.eval.runner import execute_eval_run
from app.schemas.evals import EvalCreate, EvalRunOut

router = APIRouter(tags=["evals"])


def _get_run(db, agent_id: int, run_id: int) -> EvalRun:
    run = db.get(EvalRun, run_id)
    if not run or run.agent_id != agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "evaluation not found")
    return run


@router.get("/agents/{agent_id}/evals", response_model=list[EvalRunOut])
def list_evals(agent_id: int, _admin: AgentAdminDep, db: DbDep) -> list[EvalRun]:
    return list(
        db.execute(
            select(EvalRun).where(EvalRun.agent_id == agent_id).order_by(EvalRun.created_at.desc())
        ).scalars()
    )


@router.post("/agents/{agent_id}/evals", response_model=EvalRunOut, status_code=status.HTTP_201_CREATED)
def create_eval(
    agent_id: int,
    body: EvalCreate,
    background: BackgroundTasks,
    admin: AgentAdminDep,
    db: DbDep,
) -> EvalRun:
    agent = admin.agent
    config = body.config or load_agent_config(agent)
    try:
        resolve_llm(config)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    expected = {c.expected_document_id for c in body.cases if c.expected_document_id is not None}
    if expected:
        owned = set(
            db.execute(
                select(Document.id).where(Document.workspace_id == agent.workspace_id, Document.id.in_(expected))
            ).scalars()
        )
        if missing := expected - owned:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"documents not in this agent's workspace: {sorted(missing)}")

    if body.system_prompt_id is not None:
        prompt = db.get(SystemPrompt, body.system_prompt_id)
        if not prompt or prompt.agent_id != agent_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "system prompt not in this agent")
    else:
        prompt = db.execute(
            select(SystemPrompt).where(SystemPrompt.agent_id == agent_id, SystemPrompt.is_active.is_(True))
        ).scalar_one_or_none()
    prompt_name = prompt.name if prompt else "fallback (config.yaml)"
    prompt_text = prompt.content if prompt else get_settings().chat.fallback_system_prompt

    run = EvalRun(
        agent_id=agent_id,
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


@router.get("/agents/{agent_id}/evals/{run_id}", response_model=EvalRunOut)
def get_eval(agent_id: int, run_id: int, _admin: AgentAdminDep, db: DbDep) -> EvalRun:
    return _get_run(db, agent_id, run_id)


@router.delete("/agents/{agent_id}/evals/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_eval(agent_id: int, run_id: int, _admin: AgentAdminDep, db: DbDep) -> None:
    run = _get_run(db, agent_id, run_id)
    if run.status in ("pending", "running"):
        raise HTTPException(status.HTTP_409_CONFLICT, "evaluation is still running")
    db.delete(run)
    db.commit()
