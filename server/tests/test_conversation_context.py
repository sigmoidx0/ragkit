"""Follow-up rewriting, history compression and the tool-budget answer."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError

from app.agent.context import conversation_window, fold_point, make_prepare_node
from app.agent.graph import PREPARE_NODE, _wrap_agent, build_multi_agent_graph
from app.schemas.agent_config import AgentConfig


class RecordingModel(FakeListChatModel):
    """Answers from a script and remembers every prompt it was sent."""

    prompts: list[list[BaseMessage]] = []

    def bind_tools(self, tools: Any, **kwargs: Any) -> RecordingModel:
        return self

    def _call(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> str:
        self.prompts.append(messages)
        return super()._call(messages, *args, **kwargs)


def _pairs(n: int, words: int = 50) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for i in range(n):
        out += [HumanMessage(content=f"question {i} " + "word " * words), AIMessage(content=f"answer {i} " + "word " * words)]
    return out


def test_fold_point_keeps_recent_messages_from_a_question() -> None:
    history = [*_pairs(6), HumanMessage(content="now")]
    assert fold_point(history, 0, max_tokens=100_000, keep=4) == 0  # under budget: nothing folds
    end = fold_point(history, 0, max_tokens=100, keep=4)
    assert isinstance(history[end], HumanMessage)
    assert len(history) - end >= 4


def test_window_is_summary_then_unsummarized_messages() -> None:
    history = [*_pairs(3), HumanMessage(content="now")]
    window = conversation_window({"messages": history, "summary": "talked about leave", "summarized": 4})
    assert "talked about leave" in window[0].content
    assert window[1:] == history[4:]


def test_prepare_folds_long_history_and_rewrites_the_question() -> None:
    llm = RecordingModel(responses=["summary of turns", "휴학 신청 마감일"], prompts=[])
    prepare = make_prepare_node(llm, max_tokens=100, keep_messages=2)
    history = [*_pairs(4), HumanMessage(content="그럼 마감은 언제야?")]

    update = asyncio.run(prepare({"messages": history}))

    assert update["summary"] == "summary of turns"
    assert isinstance(history[update["summarized"]], HumanMessage)
    assert update["query"] == "휴학 신청 마감일"
    # The rewrite saw the summary, not the folded messages verbatim.
    assert "summary of turns" in llm.prompts[1][1].content
    assert "question 0" not in llm.prompts[1][1].content


def test_follow_up_is_rewritten_but_first_question_costs_nothing() -> None:
    llm = RecordingModel(responses=["휴학은 학적 메뉴에서 신청합니다.", "휴학 신청 마감일", "3월 2일까지입니다."], prompts=[])
    built = build_multi_agent_graph(
        db=None,
        agent=SimpleNamespace(id=1, workspace_id=1),
        agent_cfg=AgentConfig(),
        system_prompt="",
        retrieval_mode="off",
        checkpointer=MemorySaver(),
        llm=llm,
    )
    assert PREPARE_NODE in built.graph.get_graph().nodes
    config = {"configurable": {"thread_id": "t"}}

    async def ask(text: str) -> dict:
        return await built.graph.ainvoke({"messages": [HumanMessage(content=text)], "agent_type": ""}, config)

    first = asyncio.run(ask("휴학 신청은 어떻게 해?"))
    assert first["query"] == "휴학 신청은 어떻게 해?"
    assert len(llm.prompts) == 1  # the answer only — no rewrite call

    second = asyncio.run(ask("그럼 마감은?"))
    assert second["query"] == "휴학 신청 마감일"
    assert second["messages"][-1].content == "3월 2일까지입니다."
    # The stored history keeps the user's own words.
    assert second["messages"][-2].content == "그럼 마감은?"


class _LoopingAgent:
    """A ReAct agent that searches once, then keeps going past its budget."""

    async def astream(self, payload: dict, config: dict, stream_mode: str):
        call = AIMessage(content="", tool_calls=[{"name": "retrieval", "args": {"query": "q"}, "id": "t1"}])
        yield {"messages": [*payload["messages"], call, ToolMessage(content="[4] Policy\nleave ends in March", tool_call_id="t1")]}
        raise GraphRecursionError()


def test_tool_budget_answers_from_what_was_found() -> None:
    llm = RecordingModel(responses=["3월에 끝납니다 [4]. 연장 규정은 문서에 없습니다."], prompts=[])
    node = _wrap_agent(_LoopingAgent(), max_iterations=1, llm=llm, system_prompt="be helpful")

    result = asyncio.run(node({"messages": [HumanMessage(content="휴학은 언제 끝나?")], "query": "휴학 종료"}, {}))

    assert result["messages"][0].content.startswith("3월에 끝납니다 [4]")
    final_prompt = llm.prompts[0]
    assert "leave ends in March" in final_prompt[-1].content
    assert not any(isinstance(m, ToolMessage) for m in final_prompt)


def test_regenerate_raises_only_the_answering_models_temperature() -> None:
    from unittest.mock import patch

    from app.core.config import get_settings

    models: dict[float, RecordingModel] = {}

    def model_for(cfg):
        return models.setdefault(cfg.temperature, RecordingModel(responses=[f"answer at {cfg.temperature}"], prompts=[]))

    def build(base: float, answer_temperature: float | None):
        models.clear()
        with (
            patch("app.agent.graph.resolve_llm", return_value=get_settings().llm.model_copy(update={"temperature": base})),
            patch("app.agent.graph.get_chat_model", side_effect=model_for),
        ):
            return build_multi_agent_graph(
                db=None, agent=SimpleNamespace(id=1, workspace_id=1), agent_cfg=AgentConfig(),
                system_prompt="", retrieval_mode="off", answer_temperature=answer_temperature,
            )

    built = build(0.0, 0.5)
    out = asyncio.run(built.graph.ainvoke({"messages": [HumanMessage(content="hi")], "agent_type": ""}))
    assert out["messages"][-1].content == "answer at 0.5"
    assert sorted(models) == [0.0, 0.5]  # the deterministic one still runs prepare/supervisor

    build(0.7, 0.5)  # an agent already warmer than the regenerate setting is left alone
    assert sorted(models) == [0.7]
