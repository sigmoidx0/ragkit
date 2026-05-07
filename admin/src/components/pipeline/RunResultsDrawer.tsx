import type { PipelineRunResponse } from "@/api/types";
import { Badge } from "@/components/ui";

interface RunResultsDrawerProps {
  result: PipelineRunResponse;
  onClose: () => void;
}

export function RunResultsDrawer({ result, onClose }: RunResultsDrawerProps) {
  return (
    <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex flex-col" style={{ height: 320 }}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <p className="text-sm font-semibold text-gray-800 dark:text-gray-100 flex-1">
          Results — <span className="font-normal text-gray-500 dark:text-gray-400">"{result.query}"</span>
        </p>
        <div className="flex items-center gap-2 text-[11px] text-gray-400">
          {Object.entries(result.node_timings).map(([id, ms]) => (
            <span key={id} className="font-mono">{id.slice(-6)}: {ms}ms</span>
          ))}
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-lg leading-none"
        >
          ×
        </button>
      </div>

      {/* Results */}
      <div className="overflow-y-auto flex-1 px-4 py-3 flex flex-col gap-3">
        {result.results.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500 italic">No results.</p>
        ) : (
          result.results.map((hit, i) => (
            <div key={i} className="border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold text-gray-700 dark:text-gray-200 truncate flex-1">
                  {hit.document_title ?? `Document ${hit.document_id}`}
                </span>
                <Badge tone="slate">chunk #{hit.ordinal}</Badge>
                <Badge tone="blue">{hit.score.toFixed(4)}</Badge>
              </div>
              <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed line-clamp-3">{hit.text}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
