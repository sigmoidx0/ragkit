import type { Node } from "@xyflow/react";
import type { NodeSchemaEntry } from "@/api/types";
import { Input, Label } from "@/components/ui";

interface NodeConfigPanelProps {
  node: Node;
  schema: NodeSchemaEntry | undefined;
  onChange: (nodeId: string, config: Record<string, unknown>) => void;
  readOnly?: boolean;
}

export function NodeConfigPanel({ node, schema, onChange, readOnly = false }: NodeConfigPanelProps) {
  const config = ((node.data as Record<string, unknown>)?.config as Record<string, unknown>) ?? {};
  const properties = (schema?.config_schema as Record<string, unknown>)?.properties as
    | Record<string, Record<string, unknown>>
    | undefined;

  const handleChange = (key: string, value: unknown) => {
    onChange(node.id, { ...config, [key]: value });
  };

  return (
    <div className="w-64 shrink-0 border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-y-auto">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Config</p>
          {readOnly && (
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
              read-only
            </span>
          )}
        </div>
        <p className="text-sm font-semibold text-gray-800 dark:text-gray-100 mt-0.5">
          {schema?.label ?? node.type}
        </p>
        {schema?.description && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-tight">{schema.description}</p>
        )}
      </div>

      <div className="p-4 flex flex-col gap-4">
        {!properties || Object.keys(properties).length === 0 ? (
          <p className="text-xs text-gray-400 dark:text-gray-500 italic">No configurable parameters.</p>
        ) : (
          Object.entries(properties).map(([key, fieldSchema]) => {
            const type = fieldSchema.type;
            const value = config[key] ?? fieldSchema.default ?? "";
            const isNullable = Array.isArray(type) && type.includes("null");
            const baseType = Array.isArray(type) ? type.find((t) => t !== "null") : type;

            return (
              <div key={key}>
                <Label htmlFor={`cfg-${node.id}-${key}`}>{key}</Label>
                {baseType === "boolean" ? (
                  <div className="flex items-center gap-2">
                    <input
                      id={`cfg-${node.id}-${key}`}
                      type="checkbox"
                      checked={Boolean(value)}
                      disabled={readOnly}
                      onChange={(e) => handleChange(key, e.target.checked)}
                      className="w-4 h-4 accent-teal-500 disabled:opacity-50 disabled:cursor-not-allowed"
                    />
                    <span className="text-xs text-gray-500">{String(value)}</span>
                  </div>
                ) : (
                  <Input
                    id={`cfg-${node.id}-${key}`}
                    type={baseType === "integer" || baseType === "number" ? "number" : "text"}
                    value={value === null ? "" : String(value)}
                    placeholder={isNullable ? "optional" : undefined}
                    disabled={readOnly}
                    onChange={(e) => {
                      const raw = e.target.value;
                      if (isNullable && raw === "") {
                        handleChange(key, null);
                      } else if (baseType === "integer") {
                        handleChange(key, raw === "" ? null : parseInt(raw, 10));
                      } else if (baseType === "number") {
                        handleChange(key, raw === "" ? null : parseFloat(raw));
                      } else {
                        handleChange(key, raw);
                      }
                    }}
                  />
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
