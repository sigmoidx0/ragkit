"""Pipeline graph validation."""

from __future__ import annotations

import graphlib
from typing import Any


def validate_graph(graph_json: dict[str, Any]) -> list[str]:
    """Return a list of validation error strings. Empty list means valid."""
    # Import here to ensure nodes are registered before validation
    import app.pipeline.nodes  # noqa: F401
    from app.pipeline.registry import REGISTRY

    errors: list[str] = []
    nodes: list[dict] = graph_json.get("nodes", [])
    edges: list[dict] = graph_json.get("edges", [])

    if not nodes:
        errors.append("Pipeline must have at least one node.")
        return errors

    node_map = {n["id"]: n for n in nodes}

    # Duplicate node IDs
    if len(node_map) != len(nodes):
        errors.append("Duplicate node IDs detected.")

    # All node types must exist in registry
    for node in nodes:
        if node.get("type") not in REGISTRY:
            errors.append(f"Unknown node type: {node.get('type')!r} (node id={node.get('id')!r}).")

    # Validate edges reference existing nodes and handles
    for edge in edges:
        src_id = edge.get("source")
        tgt_id = edge.get("target")
        src_handle = edge.get("sourceHandle")
        tgt_handle = edge.get("targetHandle")

        if src_id not in node_map:
            errors.append(f"Edge {edge.get('id')!r}: source node {src_id!r} not found.")
            continue
        if tgt_id not in node_map:
            errors.append(f"Edge {edge.get('id')!r}: target node {tgt_id!r} not found.")
            continue

        src_node = node_map[src_id]
        tgt_node = node_map[tgt_id]
        src_type = src_node.get("type")
        tgt_type = tgt_node.get("type")

        if src_type not in REGISTRY or tgt_type not in REGISTRY:
            continue  # already reported above

        src_outputs = {h.name: h.handle_type for h in REGISTRY[src_type].descriptor.outputs}
        tgt_inputs = {h.name: h.handle_type for h in REGISTRY[tgt_type].descriptor.inputs}

        if src_handle not in src_outputs:
            errors.append(
                f"Edge {edge.get('id')!r}: node {src_id!r} ({src_type}) has no output handle {src_handle!r}."
            )
            continue
        if tgt_handle not in tgt_inputs:
            errors.append(
                f"Edge {edge.get('id')!r}: node {tgt_id!r} ({tgt_type}) has no input handle {tgt_handle!r}."
            )
            continue

        src_htype = src_outputs[src_handle]
        tgt_htype = tgt_inputs[tgt_handle]
        if src_htype != tgt_htype:
            errors.append(
                f"Edge {edge.get('id')!r}: type mismatch — "
                f"{src_type}.{src_handle} ({src_htype}) → {tgt_type}.{tgt_handle} ({tgt_htype})."
            )

    # Exactly one QueryInput and one OutputNode
    type_counts: dict[str, int] = {}
    for node in nodes:
        t = node.get("type", "")
        type_counts[t] = type_counts.get(t, 0) + 1
    if type_counts.get("QueryInput", 0) != 1:
        errors.append("Pipeline must have exactly one QueryInput node.")
    if type_counts.get("OutputNode", 0) != 1:
        errors.append("Pipeline must have exactly one OutputNode node.")

    # Cycle detection via topological sort
    dep_graph: dict[str, set[str]] = {n["id"]: set() for n in nodes}
    for edge in edges:
        src_id = edge.get("source")
        tgt_id = edge.get("target")
        if src_id in dep_graph and tgt_id in dep_graph:
            dep_graph[tgt_id].add(src_id)

    try:
        sorter = graphlib.TopologicalSorter(dep_graph)
        list(sorter.static_order())
    except graphlib.CycleError:
        errors.append("Pipeline graph contains a cycle.")

    if errors:
        return errors

    # Orphan nodes: nodes with no edges at all
    connected_ids: set[str] = set()
    for edge in edges:
        connected_ids.add(edge.get("source", ""))
        connected_ids.add(edge.get("target", ""))
    for node in nodes:
        if node["id"] not in connected_ids:
            errors.append(f"Node {node['id']!r} ({node.get('type')}) is not connected to any edge.")

    # All required input handles must have an incoming edge
    incoming: dict[tuple[str, str], int] = {}  # (node_id, handle) → count
    for edge in edges:
        key = (edge.get("target", ""), edge.get("targetHandle", ""))
        incoming[key] = incoming.get(key, 0) + 1

    for node in nodes:
        ntype = node.get("type", "")
        if ntype not in REGISTRY:
            continue
        for handle in REGISTRY[ntype].descriptor.inputs:
            if incoming.get((node["id"], handle.name), 0) == 0:
                errors.append(
                    f"Node {node['id']!r} ({ntype}): required input handle {handle.name!r} has no incoming edge."
                )

    # Reachability: every node must lie on a path from QueryInput to OutputNode
    query_ids = [n["id"] for n in nodes if n.get("type") == "QueryInput"]
    output_ids = [n["id"] for n in nodes if n.get("type") == "OutputNode"]

    if query_ids and output_ids:
        forward_adj: dict[str, set[str]] = {n["id"]: set() for n in nodes}
        backward_adj: dict[str, set[str]] = {n["id"]: set() for n in nodes}
        for edge in edges:
            s, t = edge.get("source", ""), edge.get("target", "")
            if s in forward_adj and t in forward_adj:
                forward_adj[s].add(t)
                backward_adj[t].add(s)

        def _reachable(adj: dict[str, set[str]], starts: list[str]) -> set[str]:
            visited: set[str] = set()
            stack = list(starts)
            while stack:
                n = stack.pop()
                if n in visited:
                    continue
                visited.add(n)
                stack.extend(adj.get(n, set()))
            return visited

        reachable_from_input = _reachable(forward_adj, query_ids)
        reachable_to_output = _reachable(backward_adj, output_ids)

        for node in nodes:
            nid = node["id"]
            if nid not in reachable_from_input or nid not in reachable_to_output:
                errors.append(
                    f"Node {nid!r} ({node.get('type')}) is not on any path from QueryInput to OutputNode."
                )

    return errors
