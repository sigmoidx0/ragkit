"""Core types for the pipeline execution engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session


@dataclass
class HandleDef:
    name: str
    handle_type: str  # "query" | "vector" | "hits" | "results"


@dataclass
class NodeDescriptor:
    node_type: str
    inputs: list[HandleDef]
    outputs: list[HandleDef]
    config_schema: dict[str, Any]
    label: str = ""
    description: str = ""


@dataclass
class ExecutionContext:
    db: Session
    service_id: int
    run_inputs: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class NodeExecutor(Protocol):
    descriptor: NodeDescriptor

    def execute(
        self,
        config: dict[str, Any],
        inputs: dict[str, Any],
        ctx: ExecutionContext,
    ) -> dict[str, Any]: ...
