"""Session turns end to end: turn logs, unanswered questions, edit/regenerate, routing."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select

from app.agent import executor
from app.agent.graph import build_multi_agent_graph
from app.agent.routing import agent_profile, pick_agent
from app.api.feedback import list_unanswered
from app.db.models import Agent, ChatSession, ChatTurnLog, MessageFeedback, User, Workspace
from app.db.session import SessionLocal, create_tables
from app.rag.enrich import EnrichedHit
from app.schemas.agent_config import AgentConfig, AgentRouteConfig
from tests.test_conversation_context import RecordingModel

# Retrieval only, so the supervisor is skipped and every turn searches.
_RETRIEVAL_ONLY = AgentConfig(
    routes={
        "retrieval": AgentRouteConfig(enabled=True),
        "summary": AgentRouteConfig(enabled=False),
        "comparison": AgentRouteConfig(enabled=False),
        "direct": AgentRouteConfig(enabled=False),
    }
)
_HITS = [
    EnrichedHit(document_id=1, document_title="휴학 매뉴얼", ordinal=0, score=0.9, text="학적 메뉴에서 신청", metadata={}),
    EnrichedHit(document_id=1, document_title="휴학 매뉴얼", ordinal=1, score=0.8, text="입영통지서를 첨부", metadata={}),
]


def _session(db) -> tuple[Agent, ChatSession]:
    ws = Workspace(name="t", slug=f"turns-{id(db)}")
    user = User(email=f"turns-{id(db)}@x", hashed_password="x")
    db.add_all([ws, user])
    db.flush()
    agent = Agent(workspace_id=ws.id, name="학사")
    db.add(agent)
    db.flush()
    session = ChatSession(user_id=user.id, agent_id=agent.id)
    db.add(session)
    db.commit()
    return agent, session


def _run(db, agent: Agent, session: ChatSession, llm, saver, message: str, replace_turn: int | None = None) -> None:
    def build(*_args, **_kwargs):
        return build_multi_agent_graph(db, agent, _RETRIEVAL_ONLY, "", "on", checkpointer=saver, llm=llm)

    async def drain() -> None:
        async for _ in executor.session_agent_stream(
            db, agent.id, str(session.id), message, replace_turn=replace_turn
        ):
            pass

    with (
        patch("app.agent.checkpoint.get_checkpointer", return_value=saver),
        patch.object(executor, "_build_graph", build),
        patch("app.agent.tools.run_search", return_value=_HITS),
        patch("app.agent.graph.resolve_document_scope", return_value=[1]),
        patch("app.agent.graph.resolve_pipeline_graph", return_value=None),
    ):
        asyncio.run(drain())


def _logs(db, session_id: int) -> list[tuple[int, str, str, int]]:
    rows = db.execute(
        select(ChatTurnLog).where(ChatTurnLog.session_id == session_id).order_by(ChatTurnLog.turn_index)
    ).scalars()
    return [(r.turn_index, r.question, r.query, r.cited_count) for r in rows]


def test_turns_are_logged_and_a_replaced_turn_drops_what_followed() -> None:
    create_tables()
    saver = MemorySaver()
    llm = RecordingModel(
        responses=[
            "학적 메뉴에서 신청합니다 [1].",  # turn 0 (first question: no rewrite call)
            "휴학 신청 마감일",  # turn 1 rewrite
            "문서에서 마감일을 찾지 못했습니다.",  # turn 1 answer — cites nothing
            "휴학 신청 서류",  # edited turn 1 rewrite
            "입영통지서를 첨부합니다 [2].",  # edited turn 1 answer
            "복학은 학적 메뉴에서 합니다 [1].",  # edited first question: history is gone, no rewrite
        ],
        prompts=[],
    )
    with SessionLocal() as db:
        agent, session = _session(db)
        _run(db, agent, session, llm, saver, "휴학은 어떻게 해?")
        _run(db, agent, session, llm, saver, "그럼 마감은?")

        assert _logs(db, session.id) == [
            (0, "휴학은 어떻게 해?", "휴학은 어떻게 해?", 1),
            (1, "그럼 마감은?", "휴학 신청 마감일", 0),
        ]
        gaps = list_unanswered(agent.id, None, db)
        assert (gaps.searched, gaps.unanswered) == (2, 1)
        assert [(i.question, i.query) for i in gaps.items] == [("그럼 마감은?", "휴학 신청 마감일")]

        # A rating on the answer about to be replaced must not stick to its replacement.
        db.add(MessageFeedback(agent_id=agent.id, session_id=session.id, user_id=session.user_id,
                               turn_index=1, rating=-1, question="그럼 마감은?", answer="..."))
        db.commit()

        _run(db, agent, session, llm, saver, "그럼 서류는?", replace_turn=1)

        state = asyncio.run(saver.aget_tuple({"configurable": {"thread_id": str(session.id)}}))
        messages = state.checkpoint["channel_values"]["messages"]
        assert [(type(m), m.content) for m in messages] == [
            (HumanMessage, "휴학은 어떻게 해?"),
            (AIMessage, "학적 메뉴에서 신청합니다 [1]."),
            (HumanMessage, "그럼 서류는?"),
            (AIMessage, "입영통지서를 첨부합니다 [2]."),
        ]
        assert _logs(db, session.id)[1] == (1, "그럼 서류는?", "휴학 신청 서류", 1)
        assert db.execute(select(MessageFeedback).where(MessageFeedback.session_id == session.id)).first() is None
        assert list_unanswered(agent.id, None, db).unanswered == 0

        # Editing the very first question starts the session over.
        _run(db, agent, session, llm, saver, "복학은 어떻게 해?", replace_turn=0)
        state = asyncio.run(saver.aget_tuple({"configurable": {"thread_id": str(session.id)}}))
        assert [m.content for m in state.checkpoint["channel_values"]["messages"]] == [
            "복학은 어떻게 해?",
            "복학은 학적 메뉴에서 합니다 [1].",
        ]
        assert _logs(db, session.id) == [(0, "복학은 어떻게 해?", "복학은 어떻게 해?", 1)]


class _Picker:
    """Stands in for a chat model's structured output: always picks `agent_id`."""

    def __init__(self, agent_id: int) -> None:
        self.agent_id, self.prompt = str(agent_id), None

    def with_structured_output(self, schema: Any) -> _Picker:
        self.schema = schema
        return self

    def with_config(self, **_kwargs: Any) -> _Picker:
        return self

    async def ainvoke(self, messages: list) -> Any:
        self.prompt = messages[0].content
        return self.schema(agent_id=self.agent_id, reason="제조 표준 문서를 가진 에이전트입니다.")


def test_router_picks_among_the_workspace_agents() -> None:
    create_tables()
    with SessionLocal() as db:
        ws = Workspace(name="r", slug="routing")
        db.add(ws)
        db.flush()
        school = Agent(workspace_id=ws.id, name="학사", agent_config={"description": "학사 행정"})
        factory = Agent(workspace_id=ws.id, name="제조", agent_config={"description": "제조 표준"})
        db.add_all([school, factory])
        db.commit()

        # One agent: no model call, nothing to choose.
        assert asyncio.run(pick_agent(db, [school], "아무거나")) == (school, "")

        picker = _Picker(factory.id)
        with patch("app.agent.routing.get_chat_model", return_value=picker):
            agent, reason = asyncio.run(pick_agent(db, [school, factory], "스로틀바디 시험 항목은?"))
        assert agent is factory and reason
        assert "학사 행정" in picker.prompt and "제조 표준" in picker.prompt
        assert "documents: none" in agent_profile(db, SimpleNamespace(**{
            "id": 99, "name": "빈", "workspace_id": ws.id, "agent_config": None,
        }))
