"""MCP tools for agents: talk to a workspace's MCP servers, and wrap their tools.

Tools are built from the tool list cached on the server row (refreshed from the
admin page), so building a graph never waits on a remote server; each call
opens its own short session. A tool whose approval is "required" pauses the run
with `interrupt()` and continues only once the user approves — which needs a
checkpointer, so such tools are only offered where the run can be resumed.

Code before the `interrupt()` call runs again on resume, so the tool does
nothing there but build the request.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langgraph.config import get_config
from langgraph.types import interrupt
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, McpServer, McpToolCall, ToolCallStatus
from app.db.session import SessionLocal
from app.schemas.agent_config import AgentConfig

logger = logging.getLogger(__name__)

# Only variables with this prefix may be named as a server's token: a workspace
# admin must not be able to send, say, JWT_SECRET_KEY to a URL of their choosing.
AUTH_ENV_PREFIX = "MCP_TOKEN_"
AUTH_ENV_PATTERN = re.compile(rf"^{AUTH_ENV_PREFIX}[A-Z0-9_]{{1,100}}$")

MCP_TOOL_PREFIX = "mcp"
APPROVAL_KIND = "mcp_approval"
_TIMEOUT = timedelta(seconds=30)
_RESULT_CHARS = 4000


class McpError(Exception):
    """The server couldn't be reached, or answered with an error."""


def _headers(server: McpServer) -> dict[str, str]:
    if not server.auth_env_var:
        return {}
    token = os.getenv(server.auth_env_var)
    if not token:
        raise McpError(f"environment variable {server.auth_env_var} is not set on the ragkit server")
    return {"Authorization": f"Bearer {token}"}


async def _session_call(server: McpServer, fn):
    try:
        async with streamablehttp_client(server.url, headers=_headers(server), timeout=_TIMEOUT) as (read, write, _):
            async with ClientSession(read, write, read_timeout_seconds=_TIMEOUT) as session:
                await session.initialize()
                return await fn(session)
    except McpError:
        raise
    except BaseException as exc:  # anyio wraps failures in ExceptionGroups
        cause = exc
        while isinstance(cause, BaseExceptionGroup) and cause.exceptions:
            cause = cause.exceptions[0]
        raise McpError(f"{type(cause).__name__}: {cause}" or "connection failed") from exc


async def list_server_tools(server: McpServer) -> list[dict[str, Any]]:
    """The server's tools, as cached on its row."""
    result = await _session_call(server, lambda s: s.list_tools())
    tools = []
    for tool in result.tools:
        annotations = tool.annotations
        tools.append({
            "name": tool.name,
            "title": (annotations.title if annotations else None) or tool.title,
            "description": tool.description or "",
            "input_schema": tool.inputSchema or {"type": "object", "properties": {}},
            # Only an explicit read-only hint lets a tool skip approval by default.
            "read_only": bool(annotations and annotations.readOnlyHint),
            "destructive": bool(annotations and annotations.destructiveHint),
        })
    return tools


async def call_server_tool(server: McpServer, tool: str, args: dict[str, Any]) -> tuple[str, bool]:
    """Call a tool; returns its text output and whether the server flagged an error."""
    result = await _session_call(server, lambda s: s.call_tool(tool, args))
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        parts.append(text if text is not None else f"[{block.type} content]")
    if not parts and result.structuredContent is not None:
        parts.append(json.dumps(result.structuredContent, ensure_ascii=False))
    return "\n".join(parts)[:_RESULT_CHARS], bool(result.isError)


# ── Tools for a run ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class McpToolInfo:
    tool_name: str  # the name the model calls
    server_id: int
    server_name: str
    tool: str  # the name on the MCP server
    approval: str

    @property
    def node_id(self) -> str:
        """The graph node all of one server's tools are drawn as."""
        return f"mcp:{self.server_id}"


def mcp_tool_name(server_id: int, tool: str) -> str:
    # Provider tool names allow [A-Za-z0-9_-] and at most 64 characters.
    return f"{MCP_TOOL_PREFIX}{server_id}__{re.sub(r'[^A-Za-z0-9_-]', '_', tool)}"[:64]


def _record(**fields) -> McpToolCall:
    with SessionLocal() as db:
        call = McpToolCall(**fields)
        db.add(call)
        db.commit()
        db.refresh(call)
        db.expunge(call)
        return call


def _finish(call_id: int, result: str, is_error: bool) -> None:
    with SessionLocal() as db:
        call = db.get(McpToolCall, call_id)
        if call is not None:
            call.result, call.is_error = result, is_error
            db.commit()


def _session_id() -> int | None:
    thread_id = (get_config().get("configurable") or {}).get("thread_id")
    return int(thread_id) if thread_id is not None and str(thread_id).isdigit() else None


def _make_tool(server: McpServer, spec: dict[str, Any], approval: str, agent_id: int, user_id: int | None) -> BaseTool:
    info_name = mcp_tool_name(server.id, spec["name"])
    snapshot = McpServer(id=server.id, name=server.name, url=server.url, auth_env_var=server.auth_env_var)

    async def run(**args: Any) -> str:
        approved_args = args
        call_id: int | None = None
        if approval == "required":
            # Pauses the run. The stream records the pending call and the UI asks
            # the user; the resume brings back their decision as this value.
            decision = interrupt({
                "kind": APPROVAL_KIND,
                "server_id": server.id,
                "server_name": server.name,
                "tool": spec["name"],
                "title": spec.get("title"),
                "args": args,
            })
            call_id = decision.get("call_id")
            if decision.get("decision") != "approve":
                return "The user rejected this action, so it was not performed. Tell the user it was not done."
            approved_args = decision.get("args") or args
        else:
            # Off the event loop: a blocking write here would stall the async
            # checkpointer mid-transaction, and the two would wait on each other.
            call = await asyncio.to_thread(
                _record,
                agent_id=agent_id, session_id=_session_id(), server_id=server.id, server_name=server.name,
                tool=spec["name"], args=args, status=ToolCallStatus.auto, requested_by=user_id,
            )
            call_id = call.id
        try:
            text, is_error = await call_server_tool(snapshot, spec["name"], approved_args)
        except McpError as exc:
            text, is_error = f"Tool call failed: {exc}", True
        if call_id is not None:
            await asyncio.to_thread(_finish, call_id, text, is_error)
        if is_error:
            raise ToolException(text)  # reaches the model as an error result, not a crash
        return text

    description = spec.get("description") or spec["name"]
    return StructuredTool.from_function(
        coroutine=run,
        name=info_name,
        description=f"[{server.name}] {description}",
        args_schema=spec.get("input_schema") or {"type": "object", "properties": {}},
        handle_tool_error=True,
    )


def make_mcp_tools(
    db: Session, agent: Agent, agent_cfg: AgentConfig, user_id: int | None, interactive: bool
) -> tuple[list[BaseTool], list[McpToolInfo]]:
    """The agent's MCP tools for one run.

    `interactive` is whether this run can pause for approval (a chat session
    with a checkpointer). Without it, tools that need approval are left out —
    the model can't call what it isn't given.
    """
    if not agent_cfg.mcp_tools:
        return [], []
    servers = {
        s.id: s
        for s in db.execute(
            select(McpServer).where(
                McpServer.workspace_id == agent.workspace_id,
                McpServer.id.in_({ref.server_id for ref in agent_cfg.mcp_tools}),
                McpServer.enabled.is_(True),
            )
        ).scalars()
    }
    tools, infos = [], []
    for ref in agent_cfg.mcp_tools:
        server = servers.get(ref.server_id)
        spec = next((t for t in (server.tools or []) if t["name"] == ref.tool), None) if server else None
        if spec is None or (ref.approval == "required" and not interactive):
            continue
        tools.append(_make_tool(server, spec, ref.approval, agent.id, user_id))
        infos.append(McpToolInfo(mcp_tool_name(server.id, ref.tool), server.id, server.name, ref.tool, ref.approval))
    return tools, infos
