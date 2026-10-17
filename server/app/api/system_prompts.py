"""System prompts (per agent; editing is admin only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AgentAdminDep, AgentMemberDep, DbDep
from app.db.models import SystemPrompt
from app.schemas.system_prompts import SystemPromptCreate, SystemPromptOut, SystemPromptUpdate

router = APIRouter(tags=["system-prompts"])


@router.get("/agents/{agent_id}/system-prompts", response_model=list[SystemPromptOut])
def list_system_prompts(agent_id: int, _membership: AgentMemberDep, db: DbDep) -> list[SystemPrompt]:
    return list(
        db.execute(
            select(SystemPrompt)
            .where(SystemPrompt.agent_id == agent_id)
            .order_by(SystemPrompt.created_at.desc())
        ).scalars()
    )


@router.post(
    "/agents/{agent_id}/system-prompts",
    response_model=SystemPromptOut,
    status_code=status.HTTP_201_CREATED,
)
def create_system_prompt(
    agent_id: int,
    body: SystemPromptCreate,
    membership: AgentAdminDep,
    db: DbDep,
) -> SystemPrompt:
    prompt = SystemPrompt(
        agent_id=agent_id,
        name=body.name,
        content=body.content,
        is_active=False,
        created_by=membership.user_id,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.patch("/agents/{agent_id}/system-prompts/{prompt_id}", response_model=SystemPromptOut)
def update_system_prompt(
    agent_id: int,
    prompt_id: int,
    body: SystemPromptUpdate,
    _admin: AgentAdminDep,
    db: DbDep,
) -> SystemPrompt:
    prompt = _get_or_404(db, agent_id, prompt_id)
    if body.name is not None:
        prompt.name = body.name
    if body.content is not None:
        prompt.content = body.content
    db.commit()
    db.refresh(prompt)
    return prompt


@router.post("/agents/{agent_id}/system-prompts/{prompt_id}/activate", response_model=SystemPromptOut)
def activate_system_prompt(
    agent_id: int,
    prompt_id: int,
    _admin: AgentAdminDep,
    db: DbDep,
) -> SystemPrompt:
    # deactivate all others first
    all_prompts = db.execute(
        select(SystemPrompt).where(SystemPrompt.agent_id == agent_id)
    ).scalars()
    for p in all_prompts:
        p.is_active = False

    prompt = _get_or_404(db, agent_id, prompt_id)
    prompt.is_active = True
    db.commit()
    db.refresh(prompt)
    return prompt


@router.delete("/agents/{agent_id}/system-prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_system_prompt(
    agent_id: int,
    prompt_id: int,
    _admin: AgentAdminDep,
    db: DbDep,
) -> None:
    prompt = _get_or_404(db, agent_id, prompt_id)
    db.delete(prompt)
    db.commit()


def _get_or_404(db: Session, agent_id: int, prompt_id: int) -> SystemPrompt:
    prompt = db.execute(
        select(SystemPrompt).where(
            SystemPrompt.id == prompt_id,
            SystemPrompt.agent_id == agent_id,
        )
    ).scalar_one_or_none()
    if not prompt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "system prompt not found")
    return prompt
