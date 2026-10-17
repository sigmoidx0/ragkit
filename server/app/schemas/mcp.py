from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agent.mcp import AUTH_ENV_PATTERN, AUTH_ENV_PREFIX


def _check_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https:// (only remote MCP servers are supported)")
    return url


def _check_env(name: str | None) -> str | None:
    name = (name or "").strip() or None
    if name is not None and not AUTH_ENV_PATTERN.match(name):
        raise ValueError(f"must be an environment variable name starting with {AUTH_ENV_PREFIX}, e.g. {AUTH_ENV_PREFIX}CRM")
    return name


class McpServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=1024)
    description: str | None = Field(default=None, max_length=1000)
    # The variable holding the bearer token on the ragkit server; the token
    # itself is never sent to or stored by ragkit's API.
    auth_env_var: str | None = None

    _url = field_validator("url")(_check_url)
    _env = field_validator("auth_env_var")(_check_env)


class McpServerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, min_length=1, max_length=1024)
    description: str | None = Field(default=None, max_length=1000)
    auth_env_var: str | None = None
    enabled: bool | None = None

    @field_validator("url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return None if v is None else _check_url(v)

    _env = field_validator("auth_env_var")(_check_env)


class McpToolSpec(BaseModel):
    name: str
    title: str | None = None
    description: str = ""
    input_schema: dict[str, Any] = {}
    read_only: bool = False
    destructive: bool = False


class McpServerOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    description: str | None
    url: str
    auth_env_var: str | None
    # Whether that variable is set on the ragkit server — never its value.
    auth_configured: bool
    enabled: bool
    tools: list[McpToolSpec]
    tools_refreshed_at: datetime | None
    last_error: str | None
    used_by: list[dict[str, Any]]  # [{id, name}] of agents using its tools


class McpToolCallOut(BaseModel):
    id: int
    agent_id: int
    agent_name: str
    session_id: int | None
    server_name: str
    tool: str
    args: dict[str, Any]
    approved_args: dict[str, Any] | None
    status: str
    requested_by: str | None
    decided_by: str | None
    decided_at: datetime | None
    result: str | None
    is_error: bool
    created_at: datetime
