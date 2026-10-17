"""Pick which of a workspace's agents should take a question.

The landing page's "ask anything" box routes rather than answers: the question
goes to one agent, which answers it in its own session with its own model,
documents and citations. A hub agent that consulted every other one through
delegation would blur all of that, and delegation is capped at five agents,
one level deep.

The choice is made by config.yaml's default model, never one agent's own, from
a short profile of each agent: its name, description, document sets and a few
document titles — the description alone is often empty.
"""

from __future__ import annotations

import logging
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import create_model
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.agents import INTERNAL_LLM_TAG
from app.agent.config import load_agent_config, resolve_document_scope
from app.db.models import Agent, Document, DocumentSet
from app.llm import get_chat_model

logger = logging.getLogger(__name__)

_TITLES_PER_AGENT = 8

_PROMPT = """\
Choose the assistant best placed to answer the user's question, judging by the documents
each one has. Reply with its id and a one-sentence reason in the user's language."""


def agent_profile(db: Session, agent: Agent) -> str:
    cfg = load_agent_config(agent)
    lines = [f"id {agent.id}: {agent.name}"]
    if cfg.description:
        lines.append(f"  about: {cfg.description}")
    if cfg.document_set_ids:
        sets = db.execute(select(DocumentSet.name).where(DocumentSet.id.in_(cfg.document_set_ids))).scalars().all()
        if sets:
            lines.append(f"  document sets: {', '.join(sets)}")
    doc_ids = resolve_document_scope(db, agent.workspace_id, cfg)
    if doc_ids:
        titles = db.execute(
            select(Document.title).where(Document.id.in_(doc_ids)).order_by(Document.id).limit(_TITLES_PER_AGENT)
        ).scalars().all()
        more = f" (+{len(doc_ids) - len(titles)} more)" if len(doc_ids) > len(titles) else ""
        lines.append(f"  documents: {'; '.join(titles)}{more}")
    else:
        lines.append("  documents: none")
    return "\n".join(lines)


async def pick_agent(db: Session, agents: list[Agent], question: str) -> tuple[Agent, str]:
    """Return the agent to send `question` to, and why. Raises if the model fails."""
    if len(agents) == 1:
        return agents[0], ""
    by_id = {str(a.id): a for a in agents}
    choice_model = create_model(
        "AgentChoice",
        agent_id=(Literal[tuple(by_id)], ...),
        reason=(str, ...),
    )
    profiles = "\n\n".join(agent_profile(db, a) for a in agents)
    picker = get_chat_model().with_structured_output(choice_model).with_config(tags=[INTERNAL_LLM_TAG])
    result = await picker.ainvoke([
        SystemMessage(content=f"{_PROMPT}\n\nAssistants:\n\n{profiles}"),
        HumanMessage(content=question),
    ])
    logger.debug("[routing] %r → agent %s (%s)", question[:80], result.agent_id, result.reason)
    return by_id[result.agent_id], result.reason
