"""Text tool-call recovery — the formats small local models actually produce."""

from __future__ import annotations

from langchain_core.messages import AIMessage

from app.agent.recovery import make_tool_call_recovery_hook, parse_text_tool_calls

TOOLS = {"retrieval"}


def test_recovers_qwen_index_wrapped_call() -> None:
    # Verbatim from a real session that ended on this "answer".
    text = ' iNdEx{"name": "retrieval", "arguments": {"query": "아시아 제조 전시회 일정"}} iNdEx'
    calls = parse_text_tool_calls(text, TOOLS)
    assert [(c["name"], c["args"]) for c in calls] == [("retrieval", {"query": "아시아 제조 전시회 일정"})]


def test_recovers_fenced_and_double_encoded_arguments() -> None:
    text = 'Searching now.\n```json\n{"name": "retrieval", "arguments": "{\\"query\\": \\"휴학\\"}"}\n```'
    assert parse_text_tool_calls(text, TOOLS)[0]["args"] == {"query": "휴학"}


def test_ignores_unknown_tools_and_plain_answers() -> None:
    assert parse_text_tool_calls('{"name": "delete_everything", "arguments": {}}', TOOLS) == []
    assert parse_text_tool_calls("군휴학은 학적변동 메뉴에서 신청합니다 [1].", TOOLS) == []


def test_hook_replaces_message_in_place() -> None:
    hook = make_tool_call_recovery_hook(TOOLS)
    garbled = AIMessage(content='{"name": "retrieval", "arguments": {"query": "q"}}', id="m1")
    update = hook({"messages": [garbled]})
    (fixed,) = update["messages"]
    assert fixed.id == "m1" and fixed.content == "" and fixed.tool_calls[0]["args"] == {"query": "q"}
    # A real answer, or a message that already has structured calls, is left alone.
    assert hook({"messages": [AIMessage(content="답변입니다.")]}) == {}
