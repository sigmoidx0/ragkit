import type { DragEvent } from "react";
import type { PipelineSchema } from "@/api/types";

const HANDLE_BADGE_COLORS: Record<string, string> = {
  query: "bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300",
  vector: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  hits: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  results: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
};

interface NodePaletteProps {
  schema: PipelineSchema;
  readOnly?: boolean;
}

export function NodePalette({ schema, readOnly = false }: NodePaletteProps) {
  const onDragStart = (e: DragEvent<HTMLDivElement>, nodeType: string) => {
    if (readOnly) { e.preventDefault(); return; }
    e.dataTransfer.setData("application/reactflow-nodetype", nodeType);
    e.dataTransfer.effectAllowed = "move";
  };

  return (
    <div className="w-48 shrink-0 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 overflow-y-auto">
      <p className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
        Nodes
      </p>
      <div className="p-2 flex flex-col gap-1">
        {Object.entries(schema).map(([nodeType, entry]) => (
          <div
            key={nodeType}
            draggable={!readOnly}
            onDragStart={(e) => onDragStart(e, nodeType)}
            className={`rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 transition-all select-none ${readOnly ? "opacity-50 cursor-not-allowed" : "cursor-grab hover:border-teal-400 hover:shadow-sm"}`}
          >
            <p className="text-xs font-semibold text-gray-800 dark:text-gray-100">{entry.label}</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {entry.outputs.map((h) => (
                <span
                  key={`out-${h.name}`}
                  className={`text-[10px] font-mono px-1 rounded ${HANDLE_BADGE_COLORS[h.handle_type] ?? "bg-gray-100 text-gray-600"}`}
                >
                  {h.name}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
