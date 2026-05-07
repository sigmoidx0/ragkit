"""Pipeline graph executor: topological traversal of nodes."""

from __future__ import annotations

import graphlib
import time
from typing import Any

from app.pipeline.types import ExecutionContext


def run_pipeline(
    graph_json: dict[str, Any],
    ctx: ExecutionContext,
) -> tuple[list[Any], dict[str, float]]:
    """Execute the pipeline and return (results, node_timings).

    node_timings maps node_id → execution time in milliseconds.
    """
    import app.pipeline.nodes  # noqa: F401 — ensures executors are registered
    from app.pipeline.registry import REGISTRY

    nodes: list[dict] = graph_json["nodes"]
    edges: list[dict] = graph_json["edges"]

    node_map = {n["id"]: n for n in nodes}

    # Build dependency graph: node_id → set of node_ids it depends on
    dep_graph: dict[str, set[str]] = {n["id"]: set() for n in nodes}
    for edge in edges:
        dep_graph[edge["target"]].add(edge["source"])

    execution_order = list(graphlib.TopologicalSorter(dep_graph).static_order())

    # State holds the output dict of each node keyed by node_id
    state: dict[str, dict[str, Any]] = {}
    node_timings: dict[str, float] = {}

    for node_id in execution_order:
        node = node_map[node_id]
        node_type = node["type"]
        config = (node.get("data") or {}).get("config") or {}
        executor = REGISTRY[node_type]

        # Collect inputs from upstream edges
        inputs: dict[str, Any] = {}
        for edge in edges:
            if edge["target"] != node_id:
                continue
            src_output = state.get(edge["source"], {})
            inputs[edge["targetHandle"]] = src_output.get(edge["sourceHandle"])

        t0 = time.perf_counter()
        output = executor.execute(config, inputs, ctx)
        node_timings[node_id] = round((time.perf_counter() - t0) * 1000, 2)

        state[node_id] = output

    # Find the OutputNode and return its results
    for node in nodes:
        if node["type"] == "OutputNode":
            return state.get(node["id"], {}).get("results", []), node_timings

    return [], node_timings
