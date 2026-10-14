import { useEffect, useMemo, useState } from "react";

import type { TraceSpan } from "@/api/types";
import { cn } from "@/lib/cn";

const KIND_STYLE: Record<TraceSpan["kind"], { bar: string; icon: string; label: string }> = {
  node: { bar: "bg-teal-400 dark:bg-teal-500", icon: "◆", label: "node" },
  llm: { bar: "bg-violet-400 dark:bg-violet-500", icon: "✦", label: "LLM" },
  tool: { bar: "bg-amber-400 dark:bg-amber-500", icon: "⚙", label: "tool" },
};

function isDelegate(span: TraceSpan) {
  return span.kind === "tool" && span.name.startsWith("ask_agent_");
}

function fmtMs(ms: number) {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

/** Depth-first order, so each span sits right under its parent. */
function orderSpans(spans: TraceSpan[]): { span: TraceSpan; depth: number }[] {
  const ids = new Set(spans.map((s) => s.id));
  const children = new Map<string | null, TraceSpan[]>();
  for (const s of spans) {
    const parent = s.parent_id && ids.has(s.parent_id) ? s.parent_id : null;
    children.set(parent, [...(children.get(parent) ?? []), s]);
  }
  const out: { span: TraceSpan; depth: number }[] = [];
  const walk = (parent: string | null, depth: number) => {
    for (const s of (children.get(parent) ?? []).sort((a, b) => a.start - b.start)) {
      out.push({ span: s, depth });
      walk(s.id, depth + 1);
    }
  };
  walk(null, 0);
  return out;
}

function spanDetail(span: TraceSpan): string | null {
  const m = span.meta;
  if (span.kind === "llm" && span.end != null) {
    const tin = m.input_tokens as number | undefined;
    const tout = m.output_tokens as number | undefined;
    if (tin != null || tout != null) return `${tin ?? "?"}→${tout ?? "?"} tok`;
  }
  if (span.kind === "tool" && m.hits != null) return `${m.hits} hits`;
  if (m.error) return "error";
  return null;
}

/**
 * Waterfall of one run: every graph node, LLM call and tool call as a bar on a
 * shared timeline, nested under whatever started it. Grows live while streaming.
 */
export function TraceView({
  spans,
  streaming,
  runStartedAt,
}: {
  spans: TraceSpan[];
  streaming: boolean;
  /** performance.now() when this run's stream opened — the zero of span times. */
  runStartedAt: number | null;
}) {
  // Running spans stretch to "now", so tick while anything is still open.
  const anyOpen = spans.some((s) => s.end == null);
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (!streaming || !anyOpen || runStartedAt == null) return;
    const t = setInterval(() => setNow(performance.now() - runStartedAt), 200);
    return () => clearInterval(t);
  }, [streaming, anyOpen, runStartedAt]);

  const rows = useMemo(() => orderSpans(spans), [spans]);

  if (spans.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-xs text-gray-400 dark:text-gray-500">
        Send a message to see where the time goes.
      </div>
    );
  }

  const lastEnd = Math.max(...spans.map((s) => s.end ?? s.start));
  const total = Math.max(lastEnd, streaming ? now : 0, 1);
  const llm = spans.filter((s) => s.kind === "llm");
  const tokensIn = llm.reduce((a, s) => a + ((s.meta.input_tokens as number) ?? 0), 0);
  const tokensOut = llm.reduce((a, s) => a + ((s.meta.output_tokens as number) ?? 0), 0);
  const tools = spans.filter((s) => s.kind === "tool");

  const stats = [
    { label: "Total", value: fmtMs(total) },
    { label: "LLM calls", value: String(llm.length) },
    { label: "Tokens in/out", value: `${tokensIn.toLocaleString()} / ${tokensOut.toLocaleString()}` },
    { label: "Tool calls", value: String(tools.length) },
  ];

  return (
    <div className="flex h-full flex-col">
      <div className="grid grid-cols-2 gap-2 border-b p-3 dark:border-gray-700">
        {stats.map((s) => (
          <div key={s.label} className="rounded-lg bg-gray-50 px-2.5 py-1.5 dark:bg-gray-700/40">
            <p className="text-[10px] uppercase tracking-wide text-gray-400">{s.label}</p>
            <p className="font-mono text-sm font-semibold text-gray-800 dark:text-gray-100">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3 px-3 pt-2 text-[10px] text-gray-400">
        {Object.entries(KIND_STYLE).map(([kind, s]) => (
          <span key={kind} className="flex items-center gap-1">
            <span className={cn("inline-block h-2 w-3 rounded-sm", s.bar)} />
            {s.label}
          </span>
        ))}
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-3 rounded-sm bg-rose-400" />
          delegate
        </span>
      </div>

      <div className="flex-1 space-y-1 overflow-y-auto p-3">
        {rows.map(({ span, depth }) => {
          const end = span.end ?? (streaming ? now : span.start);
          const left = (span.start / total) * 100;
          const width = Math.max(((end - span.start) / total) * 100, 0.8);
          const running = span.end == null && streaming;
          const style = KIND_STYLE[span.kind];
          const detail = spanDetail(span);
          const label = span.kind === "tool" && span.meta.input ? `${span.name}: ${span.meta.input}` : span.name;
          return (
            <div key={span.id} className="group text-[11px]">
              <div className="flex items-center justify-between gap-2" style={{ paddingLeft: depth * 12 }}>
                <span className="flex min-w-0 items-center gap-1 text-gray-700 dark:text-gray-200">
                  <span className="text-gray-400">{style.icon}</span>
                  <span className="truncate" title={label}>
                    {label}
                  </span>
                </span>
                <span className="shrink-0 font-mono text-[10px] text-gray-400">
                  {detail && <span className="mr-1.5 text-gray-500 dark:text-gray-300">{detail}</span>}
                  {running ? "…" : fmtMs(end - span.start)}
                </span>
              </div>
              <div className="relative mt-0.5 h-2 rounded bg-gray-100 dark:bg-gray-700/50">
                <div
                  className={cn(
                    "absolute top-0 h-2 rounded",
                    isDelegate(span) ? "bg-rose-400" : style.bar,
                    running && "animate-pulse",
                  )}
                  style={{ left: `${left}%`, width: `${width}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
