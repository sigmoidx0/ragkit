"""Agent-as-tool: let one agent consult other agents.

An agent's config lists `delegates` — other agents it may ask. Each becomes a
tool on its retrieval and summary specialists. Calling it runs the delegate's
whole graph (its own documents, model and router) and hands back the answer as
plain text.

Three rules keep this safe and legible:

- One level deep. A delegate runs without delegates of its own, so agents can't
  call each other in a cycle or fan out without bound.
- Plain text across the boundary. Only the delegate's final answer crosses back,
  never its message objects — provider-specific metadata (Gemini's
  thought_signature, Anthropic's thinking blocks) doesn't survive a hop to a
  different provider.
- Membership still applies. A user only gets the delegates they could chat with
  directly, so delegation never widens what documents someone can reach.

Citations survive the hop. The delegate's sources are renumbered into the
caller's sequence (one CitationNumbering per turn) and its [N] markers rewritten
to match, so facts that came from another agent stay cited in the final answer.

The delegate runs in a fresh context so its internal LangGraph events don't leak
into the caller's stream (where its "retrieval_agent" would light up the
caller's node of the same name). Its progress is relayed instead as custom
events tagged with the delegate's node id.
"""

from __future__ import annotations

import asyncio
import contextvars
import re
from dataclasses import dataclass

from langchain_core.callbacks import adispatch_custom_event
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.config import load_agent_config, load_system_prompt
from app.db.models import Agent, SuperAdmin, WorkspaceMembership
from app.rag.citation import CitationNumbering
from app.schemas.chat import SourceItem

DELEGATE_TOOL_PREFIX = "ask_agent_"
# Custom event names relayed to the caller's stream (see executor).
DELEGATE_NODE_EVENT = "delegate_node"
DELEGATE_SOURCES_EVENT = "delegate_sources"

_CITATION = re.compile(r"(\s?)\[(\d+)\]")


@dataclass(frozen=True)
class DelegateInfo:
    agent_id: int
    name: str
    tool_name: str

    @property
    def node_id(self) -> str:
        return f"delegate:{self.agent_id}"


def delegate_tool_name(agent_id: int) -> str:
    return f"{DELEGATE_TOOL_PREFIX}{agent_id}"


def _accessible_workspace_ids(db: Session, user_id: int) -> set[int] | None:
    """Workspaces this user belongs to; None means all (superadmin)."""
    if db.get(SuperAdmin, user_id) is not None:
        return None
    return set(
        db.execute(
            select(WorkspaceMembership.workspace_id).where(WorkspaceMembership.user_id == user_id)
        ).scalars()
    )


def resolve_delegates(db: Session, own_id: int, delegate_ids: list[int], user_id: int | None) -> list[Agent]:
    """The configured delegates this user may actually reach, in config order.

    A delegate can live in another workspace, but only one the user is a member
    of — delegation never reaches documents the user couldn't open directly.
    """
    allowed = _accessible_workspace_ids(db, user_id) if user_id is not None else set()
    agents = []
    for agent_id in delegate_ids:
        agent = db.get(Agent, agent_id) if agent_id != own_id else None
        if agent is not None and (allowed is None or agent.workspace_id in allowed):
            agents.append(agent)
    return agents


def _final_answer(output: dict | None) -> str:
    messages = (output or {}).get("messages") or []
    ai = [m for m in messages if isinstance(m, AIMessage)]
    return str(ai[-1].content) if ai else ""


def renumber_sources(
    found: list[SourceItem], answer: str, numbering: CitationNumbering
) -> tuple[list[SourceItem], str]:
    """Move a delegate's sources and [N] markers into the caller's numbering.

    A marker naming no source the delegate found is dropped rather than left
    pointing at whatever the caller's source of that number happens to be.
    """
    mapping: dict[int, int] = {}
    renumbered: dict[int, SourceItem] = {}
    for s in found:
        n = numbering.number(s.document_id, s.snippet)
        mapping[s.index] = n
        renumbered.setdefault(n, s.model_copy(update={"index": n}))

    def swap(match: re.Match) -> str:
        n = mapping.get(int(match.group(2)))
        return f"{match.group(1)}[{n}]" if n is not None else ""

    return list(renumbered.values()), _CITATION.sub(swap, answer)


def make_delegate_tool(
    db: Session, agent: Agent, sources_store: dict[str, list[SourceItem]], numbering: CitationNumbering
) -> tuple[BaseTool, DelegateInfo]:
    """`sources_store` and `numbering` are the calling turn's (see graph.build_multi_agent_graph)."""
    from app.agent.graph import build_multi_agent_graph, graph_node_ids  # graph imports this module

    agent_cfg = load_agent_config(agent)
    info = DelegateInfo(agent_id=agent.id, name=agent.name, tool_name=delegate_tool_name(agent.id))
    about = agent_cfg.description or "answers from its own document collection"

    async def ask(question: str, config: RunnableConfig) -> str:
        built = build_multi_agent_graph(
            db,
            agent,
            agent_cfg,
            load_system_prompt(db, agent.id),
            retrieval_mode="on",
            allow_delegates=False,
        )
        node_ids = graph_node_ids(built.graph)
        progress: asyncio.Queue = asyncio.Queue()

        async def run_isolated() -> str:
            answer = ""
            try:
                async for ev in built.graph.astream_events(
                    {"messages": [HumanMessage(content=question)], "agent_type": ""}, version="v2"
                ):
                    kind, name = ev["event"], ev.get("name", "")
                    if kind in ("on_chain_start", "on_chain_end") and name in node_ids:
                        await progress.put({"node": name, "status": "running" if kind == "on_chain_start" else "done"})
                    elif kind == "on_chain_end" and not ev.get("parent_ids"):
                        answer = _final_answer(ev["data"].get("output"))
            finally:
                await progress.put(None)
            return answer

        # A fresh Context has no parent callbacks, so the delegate's own events
        # stay out of the caller's stream; we relay just its node progress.
        task = asyncio.create_task(run_isolated(), context=contextvars.Context())
        while (step := await progress.get()) is not None:
            await adispatch_custom_event(DELEGATE_NODE_EVENT, {"delegate": info.node_id, **step}, config=config)
        answer = await task

        found = [s for sources in built.sources_store.values() for s in sources]
        sources, answer = renumber_sources(found, answer, numbering)
        # Stored with the caller's own searches, so they're saved with the turn
        # and graded by evals like any other source of the answer.
        sources_store[f"{info.tool_name}:{question}"] = sources
        await adispatch_custom_event(
            DELEGATE_SOURCES_EVENT,
            {"delegate": info.node_id, "tool": info.tool_name, "sources": [s.model_dump() for s in sources]},
            config=config,
        )
        return f"Answer from the {agent.name} agent:\n{answer.strip() or '(no answer)'}"

    tool = StructuredTool.from_function(
        coroutine=ask,
        name=info.tool_name,
        description=(
            f"Ask the '{agent.name}' agent, which {about}. "
            "Use it for questions about that domain that your own documents don't cover. "
            "Pass a self-contained question."
        ),
    )
    return tool, info
