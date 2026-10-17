import "@xyflow/react/dist/style.css";

import { Background, BackgroundVariant, Handle, MarkerType, Position, ReactFlow } from "@xyflow/react";
import type { Edge, Node, NodeProps } from "@xyflow/react";
import { useMemo } from "react";

import type { DelegateStates, GraphEdge, GraphNode, GraphTopology, NodeStatus } from "@/api/types";
import { cn } from "@/lib/cn";

/** Per-node visual state, derived from the node_state events seen so far. */
type NodeVisual = "idle" | "running" | "done" | "static";

interface NodeData extends Record<string, unknown> {
  label: string;
  kind: GraphNode["kind"];
  visual: NodeVisual;
  /** Delegates only: the inner nodes of the delegate's own graph, in order seen. */
  inner?: [string, NodeStatus][];
}

const KIND_ACCENT: Record<GraphNode["kind"], string> = {
  entry: "border-gray-300 dark:border-gray-600",
  exit: "border-gray-300 dark:border-gray-600",
  supervisor: "border-amber-300 dark:border-amber-700",
  agent: "border-teal-300 dark:border-teal-700",
  delegate: "border-rose-300 dark:border-rose-700",
  // An MCP server: external tools, some of which wait for the user's approval.
  mcp: "border-violet-300 dark:border-violet-700",
  // Machinery that runs every turn (history compression, query rewrite).
  step: "border-gray-300 border-dashed dark:border-gray-600",
};

const VISUAL_CLS: Record<NodeVisual, string> = {
  // Unvisited nodes stay muted so the taken path reads at a glance.
  idle: "bg-white text-gray-400 opacity-60 dark:bg-gray-800 dark:text-gray-500",
  running:
    "bg-amber-50 text-amber-800 ring-2 ring-amber-300 animate-pulse dark:bg-amber-900/30 dark:text-amber-200 dark:ring-amber-700",
  done: "bg-teal-50 text-teal-800 dark:bg-teal-900/30 dark:text-teal-200",
  // Settings preview: no run in progress, so every node reads at full strength.
  static: "bg-white text-gray-700 dark:bg-gray-800 dark:text-gray-200",
};

function innerLabel(node: string) {
  return node.replace(/_agent$/, "").replace(/_/g, " ");
}

function GraphNodeBox({ data }: NodeProps) {
  const { label, kind, visual, inner } = data as NodeData;
  const isSentinel = kind === "entry" || kind === "exit";
  const isDelegate = kind === "delegate";
  const isMcp = kind === "mcp";

  return (
    <div
      className={cn(
        "select-none border px-3 py-2 text-center text-[13px] font-medium capitalize transition-colors",
        isSentinel ? "rounded-full px-4" : "rounded-lg",
        (isDelegate || isMcp) && "min-w-[140px] border-dashed",
        isMcp && "normal-case",
        KIND_ACCENT[kind],
        VISUAL_CLS[visual],
      )}
    >
      {/* Handles are hidden but required for edges to attach. */}
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      {isDelegate && (
        <span className="block text-[9px] font-semibold uppercase tracking-wider opacity-60">agent · tool</span>
      )}
      {isMcp && (
        <span className="block text-[9px] font-semibold uppercase tracking-wider opacity-60">mcp · tools</span>
      )}
      {label}
      {/* A delegate is a whole agent of its own: show its graph's progress
          nested inside, so a hand-off reads as a sub-run, not a black box. */}
      {isDelegate && inner && inner.length > 0 && (
        <span className="mt-1.5 flex flex-col gap-0.5 border-t border-rose-200 pt-1.5 text-left text-[10px] normal-case dark:border-rose-800">
          {inner.map(([node, status]) => (
            <span key={node} className="flex items-center gap-1.5">
              <span
                className={cn(
                  "inline-block h-1.5 w-1.5 rounded-full",
                  status === "running" ? "animate-pulse bg-amber-400" : "bg-teal-500",
                )}
              />
              {innerLabel(node)}
            </span>
          ))}
        </span>
      )}
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  );
}

const NODE_TYPES = { graphNode: GraphNodeBox };

const COLUMN_WIDTH = 130;
const ROW_HEIGHT = 90;
const DELEGATE_EXTRA_HEIGHT = 70;

/**
 * Place nodes in layers by distance from the entry node.
 *
 * The agent graph is shallow and fans out from the supervisor, so a layered
 * walk is enough — no layout library needed. Delegates hang off the agents that
 * call them, so they get their own row just below those agents and the exit
 * node moves one row further down to make room.
 */
function layoutNodes(nodes: GraphNode[], edges: GraphEdge[]): Map<string, { x: number; y: number }> {
  const outgoing = new Map<string, string[]>();
  for (const edge of edges) {
    if (edge.tool) continue; // tool edges aren't control flow
    outgoing.set(edge.source, [...(outgoing.get(edge.source) ?? []), edge.target]);
  }

  const entry = nodes.find((n) => n.kind === "entry")?.id ?? nodes[0]?.id;
  const depth = new Map<string, number>();
  if (entry) {
    const queue: string[] = [entry];
    depth.set(entry, 0);
    while (queue.length) {
      const current = queue.shift()!;
      for (const next of outgoing.get(current) ?? []) {
        // Keep the deepest depth so a node always sits below every predecessor.
        const candidate = depth.get(current)! + 1;
        if (candidate > (depth.get(next) ?? -1)) {
          depth.set(next, candidate);
          queue.push(next);
        }
      }
    }
  }

  const delegates = nodes.filter((n) => n.kind === "delegate");
  // Delegates and MCP servers are tools: one row below the agents that call them.
  const toolNodes = nodes.filter((n) => n.kind === "delegate" || n.kind === "mcp");
  if (toolNodes.length) {
    const callerDepth = Math.max(0, ...edges.filter((e) => e.tool).map((e) => depth.get(e.source) ?? 0));
    for (const d of toolNodes) depth.set(d.id, callerDepth + 1);
    for (const n of nodes) if (n.kind === "exit") depth.set(n.id, callerDepth + 2);
  }

  const maxDepth = Math.max(0, ...depth.values());
  const layers = new Map<number, string[]>();
  for (const node of nodes) {
    const layer = depth.get(node.id) ?? maxDepth;
    layers.set(layer, [...(layers.get(layer) ?? []), node.id]);
  }

  // A delegate grows as its inner steps appear; give the row below it room.
  const exitGap = delegates.length ? DELEGATE_EXTRA_HEIGHT : 0;
  const kindOf = new Map(nodes.map((n) => [n.id, n.kind]));

  const positions = new Map<string, { x: number; y: number }>();
  for (const [layer, ids] of layers) {
    ids.forEach((id, index) => {
      // Centre each layer on x=0 so fan-outs stay symmetrical.
      const offset = (index - (ids.length - 1) / 2) * COLUMN_WIDTH;
      const y = layer * ROW_HEIGHT + (kindOf.get(id) === "exit" ? exitGap : 0);
      positions.set(id, { x: offset, y });
    });
  }
  return positions;
}

export interface ExecutionGraphProps {
  topology: GraphTopology | null;
  /** node id → latest status seen for this run. */
  nodeStatus: Record<string, NodeStatus>;
  /** Inner progress of delegate agents, keyed by delegate node id. */
  delegateStates?: DelegateStates;
  /** True while the run is still in flight, so the entry node can read as active. */
  streaming: boolean;
  /** Draw the shape only, with no run state — used by the settings preview. */
  preview?: boolean;
  emptyMessage?: string;
}

export function ExecutionGraph({
  topology,
  nodeStatus,
  delegateStates = {},
  streaming,
  preview = false,
  emptyMessage = "Send a message to see the agent graph for this run.",
}: ExecutionGraphProps) {
  const { nodes, edges } = useMemo(() => {
    if (!topology) return { nodes: [] as Node[], edges: [] as Edge[] };

    const positions = layoutNodes(topology.nodes, topology.edges);
    const anyDone = Object.values(nodeStatus).some((s) => s === "done");

    const visualOf = (node: GraphNode): NodeVisual => {
      if (preview) return "static";
      const status = nodeStatus[node.id];
      if (status) return status;
      // The sentinels get no node_state events, so infer them from the run.
      if (node.kind === "entry") return streaming || anyDone ? "done" : "idle";
      if (node.kind === "exit") return !streaming && anyDone ? "done" : "idle";
      return "idle";
    };

    const flowNodes: Node[] = topology.nodes.map((node) => ({
      id: node.id,
      type: "graphNode",
      position: positions.get(node.id) ?? { x: 0, y: 0 },
      data: {
        label: node.label,
        kind: node.kind,
        visual: visualOf(node),
        inner: node.kind === "delegate" ? Object.entries(delegateStates[node.id] ?? {}) : undefined,
      } satisfies NodeData,
      draggable: false,
      connectable: false,
      selectable: false,
    }));

    const flowEdges: Edge[] = topology.edges.map((edge) => {
      // An edge is "taken" once its target has been entered.
      const taken = Boolean(nodeStatus[edge.target]);
      const idleStroke = preview ? "#94a3b8" : "#cbd5e1";
      const stroke = edge.tool ? (taken ? "#f43f5e" : idleStroke) : taken ? "#14b8a6" : idleStroke;
      return {
        id: `${edge.source}->${edge.target}`,
        source: edge.source,
        target: edge.target,
        animated: taken && nodeStatus[edge.target] === "running",
        // Tool edges get an arrowhead: "can call", as opposed to control flow.
        markerEnd: edge.tool ? { type: MarkerType.ArrowClosed, color: stroke, width: 14, height: 14 } : undefined,
        style: {
          strokeWidth: taken ? 2 : 1.25,
          stroke,
          strokeDasharray: edge.tool ? "2 4" : edge.conditional && !taken ? "5 4" : undefined,
        },
      };
    });

    return { nodes: flowNodes, edges: flowEdges };
  }, [topology, nodeStatus, delegateStates, streaming, preview]);

  if (!topology) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-xs text-gray-400 dark:text-gray-500">
        {emptyMessage}
      </div>
    );
  }

  return (
    <ReactFlow
      // Remount when the shape changes so fitView re-frames the new graph.
      key={topology.nodes.map((n) => n.id).join("|")}
      nodes={nodes}
      edges={edges}
      nodeTypes={NODE_TYPES}
      fitView
      fitViewOptions={{ padding: 0.12, maxZoom: 1.4 }}
      minZoom={0.3}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag
      zoomOnScroll
    >
      <Background variant={BackgroundVariant.Dots} gap={16} size={1} className="opacity-30" />
    </ReactFlow>
  );
}
