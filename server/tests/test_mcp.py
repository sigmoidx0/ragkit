"""MCP tools: which tools a run gets, the token rule, and pausing for approval."""

from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from pydantic import ValidationError

import app.agent.mcp as mcp
from app.agent.mcp import APPROVAL_KIND, make_mcp_tools, mcp_tool_name
from app.db.models import Agent, McpServer, McpToolCall, ToolCallStatus, Workspace
from app.db.session import SessionLocal, create_tables
from app.schemas.agent_config import AgentConfig, McpToolRef
from app.schemas.mcp import McpServerCreate

TOOLS = [
    {"name": "list_orders", "description": "List orders", "input_schema": {"type": "object", "properties": {}},
     "read_only": True},
    {"name": "create_order", "description": "Create an order",
     "input_schema": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
     "read_only": False},
]


def test_token_variable_must_carry_the_mcp_prefix() -> None:
    McpServerCreate(name="crm", url="https://mcp.example.com/mcp", auth_env_var="MCP_TOKEN_CRM")
    for bad in ("JWT_SECRET_KEY", "GOOGLE_API_KEY", "mcp_token_crm", "MCP_TOKEN_"):
        with pytest.raises(ValidationError):
            McpServerCreate(name="crm", url="https://mcp.example.com/mcp", auth_env_var=bad)
    with pytest.raises(ValidationError):  # stdio-style commands are not URLs
        McpServerCreate(name="crm", url="npx some-mcp-server")


def test_tool_names_fit_provider_limits() -> None:
    name = mcp_tool_name(12, "작업지시 생성/" + "x" * 80)
    assert name.startswith("mcp12__") and len(name) <= 64
    assert all(c.isascii() and (c.isalnum() or c in "_-") for c in name)


def _setup(db, slug: str):
    ws = Workspace(name=slug, slug=slug)
    db.add(ws)
    db.flush()
    on = McpServer(workspace_id=ws.id, name="desk", url="http://localhost:1/mcp", tools=TOOLS, enabled=True)
    off = McpServer(workspace_id=ws.id, name="off", url="http://localhost:2/mcp", tools=TOOLS, enabled=False)
    db.add_all([on, off])
    db.flush()
    cfg = AgentConfig(mcp_tools=[
        McpToolRef(server_id=on.id, tool="list_orders", approval="auto"),
        McpToolRef(server_id=on.id, tool="create_order", approval="required"),
        McpToolRef(server_id=off.id, tool="list_orders", approval="auto"),
        McpToolRef(server_id=on.id, tool="gone", approval="auto"),
    ])
    agent = Agent(workspace_id=ws.id, name="desk agent", agent_config=cfg.model_dump(mode="json"))
    db.add(agent)
    db.commit()
    return agent, on, cfg


def test_approval_tools_only_where_the_run_can_pause() -> None:
    create_tables()
    with SessionLocal() as db:
        agent, server, cfg = _setup(db, "mcp-scope")
        _, interactive = make_mcp_tools(db, agent, cfg, user_id=None, interactive=True)
        _, stateless = make_mcp_tools(db, agent, cfg, user_id=None, interactive=False)
    # Disabled servers and tools the server no longer lists are skipped either way.
    assert [t.tool for t in interactive] == ["list_orders", "create_order"]
    assert [t.tool for t in stateless] == ["list_orders"]


def test_a_tool_needing_approval_pauses_and_runs_only_once_approved(monkeypatch) -> None:
    create_tables()
    calls: list[tuple[str, dict]] = []

    async def fake_call(server, tool, args):
        calls.append((tool, args))
        return f"created {args['title']}", False

    monkeypatch.setattr(mcp, "call_server_tool", fake_call)
    with SessionLocal() as db:
        agent, server, cfg = _setup(db, "mcp-approval")
        tools, _ = make_mcp_tools(db, agent, cfg, user_id=None, interactive=True)
        create = next(t for t in tools if t.name.endswith("create_order"))
        call = McpToolCall(agent_id=agent.id, server_id=server.id, server_name="desk", tool="create_order",
                           args={"title": "pump"}, status=ToolCallStatus.pending)
        db.add(call)
        db.commit()
        call_id = call.id

    graph = StateGraph(MessagesState)
    graph.add_node("tools", ToolNode([create]))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    app = graph.compile(checkpointer=InMemorySaver())

    def run(thread: str, resume: dict | None) -> tuple[list, tuple]:
        cfg = {"configurable": {"thread_id": thread}}
        ask = AIMessage(content="", tool_calls=[{"name": create.name, "args": {"title": "pump"}, "id": "c1"}])

        async def go():
            await app.ainvoke({"messages": [HumanMessage("make one"), ask]}, cfg)
            interrupts = (await app.aget_state(cfg)).interrupts
            if resume is not None:
                await app.ainvoke(Command(resume={interrupts[0].id: {**resume, "call_id": call_id}}), cfg)
            return (await app.aget_state(cfg)).values["messages"], interrupts

        return asyncio.run(go())

    messages, interrupts = run("approve", {"decision": "approve", "args": {"title": "pump v2"}})
    assert interrupts[0].value["kind"] == APPROVAL_KIND
    assert interrupts[0].value["args"] == {"title": "pump"}
    # Approved with edited arguments: those are what reach the server.
    assert calls == [("create_order", {"title": "pump v2"})]
    assert isinstance(messages[-1], ToolMessage) and messages[-1].content == "created pump v2"

    calls.clear()
    messages, _ = run("reject", {"decision": "reject"})
    assert calls == []
    assert "rejected" in messages[-1].content

    with SessionLocal() as db:
        assert db.get(McpToolCall, call_id).result == "created pump v2"
