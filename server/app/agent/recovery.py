"""Recover tool calls that a model wrote as plain text.

Small local models (qwen2.5 via Ollama, for one) sometimes print a tool call
into the message body instead of emitting a structured one:

    iNdEx{"name": "retrieval", "arguments": {"query": "아시아 제조 전시회 일정"}} iNdEx

The ReAct loop only follows structured `tool_calls`, so it reads that text as
the final answer and stops — the user sees gibberish and the conversation
appears to cut off. This post-model hook spots such text and turns it back into
a real tool call so the loop carries on.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

# Start of a JSON object whose first key is "name" — every text tool-call
# format we've seen opens this way, whatever wrapper surrounds it.
_CALL_START = re.compile(r'\{\s*"name"\s*:')
_decoder = json.JSONDecoder()


def parse_text_tool_calls(text: str, tool_names: set[str]) -> list[dict[str, Any]]:
    """Extract `{"name": <known tool>, "arguments": {...}}` objects from text."""
    calls: list[dict[str, Any]] = []
    for match in _CALL_START.finditer(text):
        try:
            obj, _end = _decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict) or obj.get("name") not in tool_names:
            continue
        args = obj.get("arguments", obj.get("parameters", {}))
        if isinstance(args, str):  # some models double-encode the arguments
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                continue
        if isinstance(args, dict):
            calls.append({"name": obj["name"], "args": args, "id": f"recovered_{uuid.uuid4().hex[:12]}"})
    return calls


def make_tool_call_recovery_hook(tool_names: set[str]):
    """Build a post_model_hook for create_react_agent over these tools."""

    def recover(state: dict) -> dict:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or last.tool_calls or not isinstance(last.content, str):
            return {}
        calls = parse_text_tool_calls(last.content, tool_names)
        if not calls:
            return {}
        logger.info("recovered %d text tool call(s): %s", len(calls), [c["name"] for c in calls])
        # Same id, so add_messages replaces the garbled message instead of appending.
        return {"messages": [AIMessage(content="", tool_calls=calls, id=last.id)]}

    return recover
