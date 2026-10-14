"""Turn LangGraph's event stream into trace spans for the UI's waterfall view.

A span is one timed unit of work — a graph node, an LLM call, or a tool call —
with a parent, so the UI can nest them: a supervisor node contains its
classifier LLM call; a retrieval agent contains its searches and model turns.

Spans are reported twice, on start and on end, so the waterfall can grow live
while the run is still going.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel

SpanKind = Literal["node", "llm", "tool"]


class SpanEvent(BaseModel):
    id: str
    parent_id: str | None
    kind: SpanKind
    name: str
    phase: Literal["start", "end"]
    t_ms: float  # since the run started
    # On end: tokens for LLM spans, the query and hit count for searches, etc.
    meta: dict[str, Any] = {}


class TraceRecorder:
    def __init__(self, graph_nodes: set[str]) -> None:
        self._t0 = time.perf_counter()
        self._graph_nodes = graph_nodes
        self._open: dict[str, SpanKind] = {}  # run_id → kind, for spans still running
        self._known: set[str] = set()  # every span ever opened, to resolve parents

    def _now(self) -> float:
        return round((time.perf_counter() - self._t0) * 1000, 1)

    def _parent(self, event: dict) -> str | None:
        # parent_ids runs root → immediate parent; the nearest one we track wins.
        for run_id in reversed(event.get("parent_ids") or []):
            if run_id in self._known:
                return run_id
        return None

    def _kind_of(self, event: dict) -> tuple[SpanKind, str] | None:
        kind, name = event["event"], event.get("name", "")
        if kind in ("on_chain_start", "on_chain_end") and name in self._graph_nodes:
            return "node", name
        if kind in ("on_chat_model_start", "on_chat_model_end"):
            model = (event.get("metadata") or {}).get("ls_model_name") or name
            return "llm", model
        if kind in ("on_tool_start", "on_tool_end", "on_tool_error"):
            return "tool", name
        return None

    def observe(self, event: dict, meta: dict[str, Any] | None = None) -> SpanEvent | None:
        """Return the span event for this LangGraph event, if it opens or closes one."""
        classified = self._kind_of(event)
        if classified is None:
            return None
        kind, name = classified
        run_id = event.get("run_id", "")
        is_start = event["event"].endswith("_start")

        if is_start:
            self._open[run_id] = kind
            self._known.add(run_id)
        elif run_id not in self._open:
            return None
        else:
            del self._open[run_id]

        span_meta = dict(meta or {})
        if kind == "llm" and not is_start:
            usage = getattr((event.get("data") or {}).get("output"), "usage_metadata", None) or {}
            span_meta.update(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
            )
        if event["event"] == "on_tool_error":
            span_meta["error"] = True

        return SpanEvent(
            id=run_id,
            parent_id=self._parent(event),
            kind=kind,
            name=name,
            phase="start" if is_start else "end",
            t_ms=self._now(),
            meta=span_meta,
        )
