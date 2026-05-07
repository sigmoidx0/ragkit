/**
 * Custom React Flow node components for each pipeline node type.
 * Defined outside the page component to prevent infinite re-renders.
 */
import type { NodeProps } from "@xyflow/react";
import { PipelineNodeBase } from "./PipelineNodeBase";

const makeNode = (
  nodeType: string,
  label: string,
  inputHandles: Array<{ name: string; handle_type: string }>,
  outputHandles: Array<{ name: string; handle_type: string }>,
  accentColor: string,
) =>
  function PipelineNode(props: NodeProps) {
    return (
      <PipelineNodeBase
        {...props}
        config={{ nodeType, label, inputHandles, outputHandles, accentColor }}
      />
    );
  };

export const QueryInputNode = makeNode(
  "QueryInput",
  "Query Input",
  [],
  [{ name: "query", handle_type: "query" }],
  "border-teal-300 dark:border-teal-700",
);

export const EmbedNode = makeNode(
  "EmbedNode",
  "Embed",
  [{ name: "query", handle_type: "query" }],
  [{ name: "vector", handle_type: "vector" }],
  "border-amber-300 dark:border-amber-700",
);

export const RetrieveNode = makeNode(
  "RetrieveNode",
  "Retrieve",
  [
    { name: "vector", handle_type: "vector" },
    { name: "query", handle_type: "query" },
  ],
  [{ name: "hits", handle_type: "hits" }],
  "border-blue-300 dark:border-blue-700",
);

export const RerankNode = makeNode(
  "RerankNode",
  "Rerank",
  [
    { name: "hits", handle_type: "hits" },
    { name: "query", handle_type: "query" },
  ],
  [{ name: "hits", handle_type: "hits" }],
  "border-purple-300 dark:border-purple-700",
);

export const EnrichNode = makeNode(
  "EnrichNode",
  "Enrich",
  [{ name: "hits", handle_type: "hits" }],
  [{ name: "results", handle_type: "results" }],
  "border-indigo-300 dark:border-indigo-700",
);

export const OutputNode = makeNode(
  "OutputNode",
  "Output",
  [{ name: "results", handle_type: "results" }],
  [],
  "border-green-300 dark:border-green-700",
);

export const NODE_TYPES = {
  QueryInput: QueryInputNode,
  EmbedNode,
  RetrieveNode,
  RerankNode,
  EnrichNode,
  OutputNode,
} as const;
