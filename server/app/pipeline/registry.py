"""Node executor registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.pipeline.types import NodeDescriptor, NodeExecutor

REGISTRY: dict[str, "NodeExecutor"] = {}


def register(executor: "NodeExecutor") -> "NodeExecutor":
    REGISTRY[executor.descriptor.node_type] = executor
    return executor


def get_node_schema() -> dict[str, Any]:
    return {
        key: {
            "label": ex.descriptor.label or key,
            "description": ex.descriptor.description,
            "inputs": [{"name": h.name, "handle_type": h.handle_type} for h in ex.descriptor.inputs],
            "outputs": [{"name": h.name, "handle_type": h.handle_type} for h in ex.descriptor.outputs],
            "config_schema": ex.descriptor.config_schema,
        }
        for key, ex in REGISTRY.items()
    }
