import { useEffect, useState } from "react";

import type { DelegateStates, GraphTopology, NodeStatus, TraceSpan } from "@/api/types";
import { ExecutionGraph } from "@/components/chat/ExecutionGraph";
import { TraceView } from "@/components/chat/TraceView";
import { cn } from "@/lib/cn";

type Tab = "graph" | "trace";

export interface RunState {
  topology: GraphTopology | null;
  nodeStatus: Record<string, NodeStatus>;
  delegateStates: DelegateStates;
  spans: TraceSpan[];
  /** performance.now() when the run's stream opened. */
  runStartedAt: number | null;
}

function ExpandIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5">
      <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" />
    </svg>
  );
}

function Tabs({ tab, onChange }: { tab: Tab; onChange: (t: Tab) => void }) {
  return (
    <div className="inline-flex rounded-lg border border-gray-200 p-0.5 text-xs dark:border-gray-600">
      {(["graph", "trace"] as Tab[]).map((t) => (
        <button
          key={t}
          onClick={() => onChange(t)}
          className={cn(
            "rounded-md px-2.5 py-1 capitalize transition-colors",
            tab === t
              ? "bg-teal-500 text-white"
              : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200",
          )}
        >
          {t}
        </button>
      ))}
    </div>
  );
}

/**
 * Side panel showing how the latest run executed: the agent graph lighting up
 * as it goes, or a timing waterfall. Expands to a full-screen view with both
 * side by side.
 */
export function RunInspector({
  run,
  streaming,
  onHide,
}: {
  run: RunState;
  streaming: boolean;
  onHide: () => void;
}) {
  const [tab, setTab] = useState<Tab>("graph");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setExpanded(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded]);

  const graph = (
    <ExecutionGraph
      topology={run.topology}
      nodeStatus={run.nodeStatus}
      delegateStates={run.delegateStates}
      streaming={streaming}
    />
  );
  const trace = <TraceView spans={run.spans} streaming={streaming} runStartedAt={run.runStartedAt} />;

  return (
    <>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between gap-2 border-b px-3 py-2 dark:border-gray-700">
          <Tabs tab={tab} onChange={setTab} />
          <div className="flex items-center gap-1">
            <button
              onClick={() => setExpanded(true)}
              title="Expand"
              className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-200"
            >
              <ExpandIcon />
            </button>
            <button
              onClick={onHide}
              className="rounded-md px-1.5 py-1 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            >
              Hide
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1">{tab === "graph" ? graph : trace}</div>
      </div>

      {expanded && (
        <div className="fixed inset-0 z-50 flex bg-black/40 p-4 backdrop-blur-sm md:p-8" onClick={() => setExpanded(false)}>
          <div
            className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl bg-white shadow-2xl dark:bg-gray-800"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b px-5 py-3 dark:border-gray-700">
              <div>
                <p className="text-sm font-bold text-gray-800 dark:text-gray-100">Run inspector</p>
                <p className="text-[11px] text-gray-400">
                  {streaming ? "Live — updating as the agent runs" : "Latest run"}
                </p>
              </div>
              <button
                onClick={() => setExpanded(false)}
                className="rounded-lg px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
              >
                Close (Esc)
              </button>
            </div>
            <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
              <div className="min-h-[50vh] border-b lg:border-b-0 lg:border-r dark:border-gray-700">{graph}</div>
              <div className="min-h-0">{trace}</div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
