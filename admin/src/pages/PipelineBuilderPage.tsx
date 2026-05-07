import "@xyflow/react/dist/style.css";

import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
  type Edge,
  type IsValidConnection,
  type Node,
  type OnConnect,
} from "@xyflow/react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

type RunPhase = "idle" | "checking" | "preparing" | "running";

const COMPONENT_LABELS: Record<string, string> = {
  embedder: "임베딩 모델",
  reranker: "리랭커 모델",
};
import { toast } from "sonner";

import { PipelineApi } from "@/api/endpoints";
import type { Pipeline, PipelineGraph, PipelineRunResponse, PipelineSchema, PipelineStatus } from "@/api/types";
import { NodeConfigPanel } from "@/components/pipeline/NodeConfigPanel";
import { NodePalette } from "@/components/pipeline/NodePalette";
import { RunResultsDrawer } from "@/components/pipeline/RunResultsDrawer";
import { NODE_TYPES } from "@/components/pipeline/pipelineNodes";
import { Button, Input } from "@/components/ui";
import { useService } from "@/services/ServiceProvider";

// Node handle type maps derived from the node definitions
const NODE_OUTPUT_HANDLE_TYPES: Record<string, Record<string, string>> = {
  QueryInput: { query: "query" },
  EmbedNode: { vector: "vector" },
  RetrieveNode: { hits: "hits" },
  RerankNode: { hits: "hits" },
  EnrichNode: { results: "results" },
  OutputNode: {},
};
const NODE_INPUT_HANDLE_TYPES: Record<string, Record<string, string>> = {
  QueryInput: {},
  EmbedNode: { query: "query" },
  RetrieveNode: { vector: "vector", query: "query" },
  RerankNode: { hits: "hits", query: "query" },
  EnrichNode: { hits: "hits" },
  OutputNode: { results: "results" },
};

let nodeCounter = 0;
function newNodeId() {
  nodeCounter += 1;
  return `node-${nodeCounter}`;
}

const EXAMPLE_PIPELINE: { nodes: Node[]; edges: Edge[] } = {
  nodes: [
    { id: "ex-1", type: "QueryInput",  position: { x: 80,  y: 160 }, data: { config: {} } },
    { id: "ex-2", type: "EmbedNode",   position: { x: 280, y: 60  }, data: { config: {} } },
    { id: "ex-3", type: "RetrieveNode",position: { x: 520, y: 120 }, data: { config: {} } },
    { id: "ex-4", type: "RerankNode",  position: { x: 760, y: 60  }, data: { config: {} } },
    { id: "ex-5", type: "EnrichNode",  position: { x: 1000,y: 120 }, data: { config: {} } },
    { id: "ex-6", type: "OutputNode",  position: { x: 1200,y: 200 }, data: { config: {} } },
  ],
  edges: [
    { id: "ex-e1", source: "ex-1", target: "ex-2", sourceHandle: "query",  targetHandle: "query"   },
    { id: "ex-e2", source: "ex-1", target: "ex-3", sourceHandle: "query",  targetHandle: "query"   },
    { id: "ex-e3", source: "ex-2", target: "ex-3", sourceHandle: "vector", targetHandle: "vector"  },
    { id: "ex-e4", source: "ex-3", target: "ex-4", sourceHandle: "hits",   targetHandle: "hits"    },
    { id: "ex-e5", source: "ex-1", target: "ex-4", sourceHandle: "query",  targetHandle: "query"   },
    { id: "ex-e6", source: "ex-4", target: "ex-5", sourceHandle: "hits",   targetHandle: "hits"    },
    { id: "ex-e7", source: "ex-5", target: "ex-6", sourceHandle: "results",targetHandle: "results" },
  ],
};

function graphToFlow(graph: PipelineGraph): { nodes: Node[]; edges: Edge[] } {
  return {
    nodes: graph.nodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: { config: n.data?.config ?? {} },
    })),
    edges: graph.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle,
      targetHandle: e.targetHandle,
    })),
  };
}

function flowToGraph(nodes: Node[], edges: Edge[]): PipelineGraph {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type ?? "Unknown",
      position: n.position,
      data: { config: (n.data as Record<string, unknown>)?.config as Record<string, unknown> ?? {} },
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle ?? "",
      targetHandle: e.targetHandle ?? "",
    })),
  };
}

const STATUS_STYLES: Record<string, string> = {
  draft:    "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400",
  active:   "bg-teal-50 text-teal-600 dark:bg-teal-900/40 dark:text-teal-300",
  archived: "bg-amber-50 text-amber-600 dark:bg-amber-900/40 dark:text-amber-400",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`text-xs font-semibold px-2.5 py-1 rounded-xl capitalize ${STATUS_STYLES[status] ?? STATUS_STYLES.draft}`}>
      {status}
    </span>
  );
}

export default function PipelineBuilderPage() {
  const { current: service } = useService();
  const isAdmin = service?.role === "admin";
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [pipelineName, setPipelineName] = useState("Untitled Pipeline");
  const [activePipelineId, setActivePipelineId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [runResult, setRunResult] = useState<PipelineRunResponse | null>(null);
  const [runPhase, setRunPhase] = useState<RunPhase>("idle");
  const [preparingLabels, setPreparingLabels] = useState<string[]>([]);

  const selectedNode = selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) ?? null : null;

  // Schema query
  const { data: schema = {} as PipelineSchema } = useQuery({
    queryKey: ["pipeline-schema"],
    queryFn: PipelineApi.schema,
    staleTime: Infinity,
    enabled: !!service,
  });

  // Pipelines list
  const { data: pipelines = [], refetch: refetchPipelines } = useQuery({
    queryKey: ["pipelines", service?.id],
    queryFn: () => PipelineApi.list(service!.id),
    enabled: !!service,
  });

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!service) throw new Error("No service selected");
      const graph = flowToGraph(nodes, edges);
      if (activePipelineId != null) {
        return PipelineApi.update(service.id, activePipelineId, { name: pipelineName, graph_json: graph });
      }
      return PipelineApi.create(service.id, { name: pipelineName, graph_json: graph });
    },
    onSuccess: (saved: Pipeline) => {
      setActivePipelineId(saved.id);
      toast.success("Pipeline saved.");
      void refetchPipelines();
    },
    onError: (e: unknown) => {
      const msg = e instanceof Error ? e.message : "Save failed";
      toast.error(msg);
    },
  });

  const [activePipelineStatus, setActivePipelineStatus] = useState<PipelineStatus>("draft");

  const statusMutation = useMutation({
    mutationFn: (newStatus: PipelineStatus) => {
      if (!service || activePipelineId == null) throw new Error("No pipeline selected");
      return PipelineApi.setStatus(service.id, activePipelineId, newStatus);
    },
    onSuccess: (updated: Pipeline) => {
      setActivePipelineStatus(updated.status);
      void refetchPipelines();
      toast.success(`Pipeline ${updated.status}.`);
    },
    onError: (e: unknown) => {
      const raw = e instanceof Error ? e.message : "Status update failed";
      let msg = raw;
      try { msg = JSON.parse(raw).detail?.map?.((d: { msg: string }) => d.msg).join(", ") ?? raw; } catch { /* ignore */ }
      toast.error(msg);
    },
  });

  const handleRun = useCallback(async () => {
    if (!service || activePipelineId == null || !query.trim()) return;
    try {
      setRunPhase("checking");
      const readiness = await PipelineApi.readiness(service.id, activePipelineId);

      if (!readiness.ready) {
        const cold = Object.entries(readiness.components)
          .filter(([, loaded]) => !loaded)
          .map(([name]) => COMPONENT_LABELS[name] ?? name);
        setPreparingLabels(cold);
        setRunPhase("preparing");
        await PipelineApi.prepare(service.id, activePipelineId);
      }

      setRunPhase("running");
      const result = await PipelineApi.run(service.id, activePipelineId, { query, top_k: topK });
      setRunResult(result);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Run failed");
    } finally {
      setRunPhase("idle");
      setPreparingLabels([]);
    }
  }, [service, activePipelineId, query, topK]);

  // Connection validation: only allow same handle_type
  const isValidConnection: IsValidConnection = useCallback(
    (connection) => {
      const srcNode = nodes.find((n) => n.id === connection.source);
      const tgtNode = nodes.find((n) => n.id === connection.target);
      if (!srcNode || !tgtNode) return false;
      const srcType = srcNode.type ?? "";
      const tgtType = tgtNode.type ?? "";
      const srcHandle = connection.sourceHandle ?? "";
      const tgtHandle = connection.targetHandle ?? "";
      const srcHType = NODE_OUTPUT_HANDLE_TYPES[srcType]?.[srcHandle];
      const tgtHType = NODE_INPUT_HANDLE_TYPES[tgtType]?.[tgtHandle];
      return !!srcHType && srcHType === tgtHType;
    },
    [nodes],
  );

  const onConnect: OnConnect = useCallback(
    (connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges],
  );

  // Drag-and-drop from palette
  const onDragOver = useCallback((e: React.DragEvent) => {
    if (!isAdmin) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }, [isAdmin]);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      if (!isAdmin) return;
      e.preventDefault();
      const nodeType = e.dataTransfer.getData("application/reactflow-nodetype");
      if (!nodeType || !reactFlowWrapper.current) return;

      const rect = reactFlowWrapper.current.getBoundingClientRect();
      const position = { x: e.clientX - rect.left - 80, y: e.clientY - rect.top - 30 };

      const newNode: Node = {
        id: newNodeId(),
        type: nodeType,
        position,
        data: { config: {} },
      };
      setNodes((nds) => [...nds, newNode]);
    },
    [setNodes],
  );

  // Config panel update
  const handleConfigChange = useCallback(
    (nodeId: string, config: Record<string, unknown>) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, config } } : n)),
      );
    },
    [setNodes],
  );

  // Load a saved pipeline
  const loadPipeline = (p: Pipeline) => {
    const { nodes: flowNodes, edges: flowEdges } = graphToFlow(p.graph_json);
    setNodes(flowNodes);
    setEdges(flowEdges);
    setPipelineName(p.name);
    setActivePipelineId(p.id);
    setActivePipelineStatus(p.status);
    setSelectedNodeId(null);
    setRunResult(null);
  };

  const newPipeline = () => {
    setNodes([]);
    setEdges([]);
    setPipelineName("Untitled Pipeline");
    setActivePipelineId(null);
    setActivePipelineStatus("draft");
    setSelectedNodeId(null);
    setRunResult(null);
  };

  const loadExample = () => {
    setNodes(EXAMPLE_PIPELINE.nodes);
    setEdges(EXAMPLE_PIPELINE.edges);
    setPipelineName("Example RAG Pipeline");
    setActivePipelineId(null);
    setSelectedNodeId(null);
    setRunResult(null);
  };

  const isEmpty = nodes.length === 0;

  return (
    <div className="-mx-4 -mb-10 md:-mx-8 flex flex-col" style={{ height: "calc(100vh - 81px)" }}>
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shrink-0 flex-wrap">
        {/* Pipeline selector */}
        <select
          value={activePipelineId ?? ""}
          onChange={(e) => {
            const val = e.target.value;
            if (val === "") {
              newPipeline();
            } else {
              const p = pipelines.find((pl) => pl.id === Number(val));
              if (p) loadPipeline(p);
            }
          }}
          className="text-sm border border-gray-200 dark:border-gray-600 rounded-xl px-3 py-1.5 bg-white dark:bg-gray-700 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-teal-100 max-w-[180px]"
        >
          <option value="">+ New Pipeline</option>
          {pipelines.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>

        <Input
          value={pipelineName}
          onChange={(e) => setPipelineName(e.target.value)}
          className="w-40 text-sm py-1.5"
          placeholder="Pipeline name"
        />

        {isAdmin ? (
          <>
            <Button
              size="sm"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              {saveMutation.isPending ? "Saving…" : "Save"}
            </Button>
            {activePipelineId != null && (
              <>
                <StatusBadge status={activePipelineStatus} />
                {activePipelineStatus !== "active" && activePipelineStatus !== "archived" && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => statusMutation.mutate("active")}
                    disabled={statusMutation.isPending}
                  >
                    Activate
                  </Button>
                )}
                {activePipelineStatus === "active" && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => statusMutation.mutate("draft")}
                    disabled={statusMutation.isPending}
                  >
                    Deactivate
                  </Button>
                )}
                {activePipelineStatus !== "archived" && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => statusMutation.mutate("archived")}
                    disabled={statusMutation.isPending}
                  >
                    Archive
                  </Button>
                )}
              </>
            )}
          </>
        ) : (
          <span className="text-xs font-medium px-2.5 py-1.5 rounded-xl bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
            Read-only
          </span>
        )}

        <div className="flex-1" />

        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-56 text-sm py-1.5"
          placeholder="Run query…"
          onKeyDown={(e) => { if (e.key === "Enter") void handleRun(); }}
        />
        <Input
          type="number"
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
          className="w-16 text-sm py-1.5 text-center"
          min={1}
          max={200}
        />
        <Button
          size="sm"
          variant="secondary"
          onClick={() => void handleRun()}
          disabled={runPhase !== "idle" || !activePipelineId || !query.trim()}
        >
          {runPhase === "checking" && "확인 중…"}
          {runPhase === "preparing" && `${preparingLabels.join(", ")} 로드 중…`}
          {runPhase === "running" && "실행 중…"}
          {runPhase === "idle" && "Run"}
        </Button>
      </div>

      {/* Main body */}
      <div className="flex flex-1 min-h-0">
        {/* Node palette */}
        <NodePalette schema={schema} readOnly={!isAdmin} />

        {/* Canvas */}
        <div ref={reactFlowWrapper} className="flex-1 min-w-0 relative">
          {isEmpty && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center pointer-events-none">
              <div className="pointer-events-auto flex flex-col items-center gap-4 p-8 rounded-2xl bg-white/80 dark:bg-gray-800/80 backdrop-blur border border-gray-200 dark:border-gray-700 shadow-lg max-w-sm text-center">
                <div className="text-4xl">🔗</div>
                <div>
                  <p className="font-semibold text-gray-800 dark:text-gray-100 mb-1">파이프라인을 구성하세요</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">왼쪽 팔레트에서 노드를 드래그하거나,<br />예시 파이프라인으로 시작해 보세요.</p>
                </div>
                <button
                  onClick={loadExample}
                  className="px-4 py-2 rounded-xl bg-teal-500 hover:bg-teal-600 text-white text-sm font-medium transition-colors"
                >
                  예시 파이프라인 불러오기
                </button>
              </div>
            </div>
          )}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={isAdmin ? onConnect : undefined}
            onDrop={onDrop}
            onDragOver={onDragOver}
            isValidConnection={isValidConnection}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            onPaneClick={() => setSelectedNodeId(null)}
            nodesDraggable={isAdmin}
            nodesConnectable={isAdmin}
            deleteKeyCode={isAdmin ? "Backspace" : null}
            fitView
            className="bg-gray-50 dark:bg-gray-900"
          >
            <Background variant={BackgroundVariant.Dots} gap={16} size={1} className="opacity-30" />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                const colors: Record<string, string> = {
                  QueryInput: "#2dd4bf",
                  EmbedNode: "#fbbf24",
                  RetrieveNode: "#60a5fa",
                  RerankNode: "#a78bfa",
                  EnrichNode: "#818cf8",
                  OutputNode: "#34d399",
                };
                return colors[n.type ?? ""] ?? "#9ca3af";
              }}
            />
          </ReactFlow>
        </div>

        {/* Config panel */}
        {selectedNode && (
          <NodeConfigPanel
            node={selectedNode}
            schema={schema[selectedNode.type ?? ""]}
            onChange={handleConfigChange}
            readOnly={!isAdmin}
          />
        )}
      </div>

      {/* Run results drawer */}
      {runResult && (
        <RunResultsDrawer result={runResult} onClose={() => setRunResult(null)} />
      )}
    </div>
  );
}
