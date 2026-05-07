import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import { cn } from "@/lib/cn";

export interface PipelineNodeConfig {
  nodeType: string;
  label: string;
  description?: string;
  inputHandles?: Array<{ name: string; handle_type: string }>;
  outputHandles?: Array<{ name: string; handle_type: string }>;
  accentColor?: string;
}

const HANDLE_COLORS: Record<string, string> = {
  query: "bg-teal-400 border-teal-500",
  vector: "bg-amber-400 border-amber-500",
  hits: "bg-blue-400 border-blue-500",
  results: "bg-green-400 border-green-500",
};

const HANDLE_LABEL_COLORS: Record<string, string> = {
  query: "text-teal-600 dark:text-teal-400",
  vector: "text-amber-600 dark:text-amber-400",
  hits: "text-blue-600 dark:text-blue-400",
  results: "text-green-600 dark:text-green-400",
};

interface PipelineNodeBaseProps extends NodeProps {
  config: PipelineNodeConfig;
}

export function PipelineNodeBase({ selected, config }: PipelineNodeBaseProps) {
  const { label, description, inputHandles = [], outputHandles = [], accentColor = "border-gray-300 dark:border-gray-600" } = config;

  return (
    <div
      className={cn(
        "rounded-lg border-2 bg-white dark:bg-gray-800 shadow-sm min-w-[160px] select-none",
        selected ? "border-teal-400 shadow-teal-200 dark:shadow-teal-900 shadow-md" : accentColor,
      )}
    >
      {/* Input handles */}
      {inputHandles.map((h, i) => (
        <Handle
          key={`in-${h.name}`}
          type="target"
          position={Position.Left}
          id={h.name}
          style={{ top: `${((i + 1) / (inputHandles.length + 1)) * 100}%` }}
          className={cn("!w-3 !h-3 !border-2", HANDLE_COLORS[h.handle_type] ?? "bg-gray-400 border-gray-500")}
        />
      ))}

      {/* Header */}
      <div className={cn("px-3 py-2 border-b dark:border-gray-700 rounded-t-lg", selected ? "bg-teal-50 dark:bg-teal-900/20" : "bg-gray-50 dark:bg-gray-700/50")}>
        <p className="text-xs font-semibold text-gray-800 dark:text-gray-100 leading-tight">{label}</p>
      </div>

      {/* Handle labels */}
      {(inputHandles.length > 0 || outputHandles.length > 0) && (
        <div className="px-3 py-2 flex justify-between gap-4 text-[10px]">
          <div className="flex flex-col gap-1">
            {inputHandles.map(h => (
              <span key={h.name} className={cn("font-mono", HANDLE_LABEL_COLORS[h.handle_type] ?? "text-gray-500")}>
                ← {h.name}
              </span>
            ))}
          </div>
          <div className="flex flex-col gap-1 items-end">
            {outputHandles.map(h => (
              <span key={h.name} className={cn("font-mono", HANDLE_LABEL_COLORS[h.handle_type] ?? "text-gray-500")}>
                {h.name} →
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Output handles */}
      {outputHandles.map((h, i) => (
        <Handle
          key={`out-${h.name}`}
          type="source"
          position={Position.Right}
          id={h.name}
          style={{ top: `${((i + 1) / (outputHandles.length + 1)) * 100}%` }}
          className={cn("!w-3 !h-3 !border-2", HANDLE_COLORS[h.handle_type] ?? "bg-gray-400 border-gray-500")}
        />
      ))}
    </div>
  );
}
