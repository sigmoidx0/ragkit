export interface User {
  id: number;
  email: string;
  is_superadmin: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export type DocumentStatus = "pending" | "chunking" | "embedding" | "indexed" | "failed";

// ---------------------------------------------------------------------------
// Chunk config
// ---------------------------------------------------------------------------

export interface RecursiveChunkConfig {
  strategy: "recursive";
  chunk_size?: number;
  chunk_overlap?: number;
}

export interface MarkdownHeaderChunkConfig {
  strategy: "markdown_header";
  headers_to_split_on?: string[];
  chunk_size?: number;
  chunk_overlap?: number;
}

export interface CharacterChunkConfig {
  strategy: "character";
  separator?: string;
  chunk_size?: number;
  chunk_overlap?: number;
}

export interface TokenChunkConfig {
  strategy: "token";
  chunk_size?: number;
  chunk_overlap?: number;
  encoding_name?: string;
}

export interface RegexChunkConfig {
  strategy: "regex";
  pattern: string;
  chunk_size?: number;
  chunk_overlap?: number;
}

export type ChunkConfig =
  | RecursiveChunkConfig
  | MarkdownHeaderChunkConfig
  | CharacterChunkConfig
  | TokenChunkConfig
  | RegexChunkConfig;

export interface ChunkPreviewChunk {
  ordinal: number;
  text: string;
  char_count: number;
  metadata: Record<string, unknown>;
}

export interface ChunkPreviewResponse {
  markdown: string;
  markdown_truncated: boolean;
  chunks: ChunkPreviewChunk[];
  total_chunks: number;
}

export type ServiceRole = "admin" | "member" | "viewer";

export interface Service {
  id: number;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
}

export interface ServiceWithRole extends Service {
  role: ServiceRole;
}

// ── Agent configuration (a Service is presented as an Agent) ──────────────────

export type LlmProvider = "openai" | "anthropic" | "google" | "ollama" | "vllm";
export type AgentRouteName = "retrieval" | "summary" | "comparison" | "direct";
export type AgentAccent = "teal" | "blue" | "purple" | "amber" | "rose" | "slate";

export interface AgentRouteConfig {
  enabled: boolean;
  description: string;
}

export interface AgentConfig {
  description: string;
  /** null keeps the name-based theme. */
  icon: string | null;
  accent: AgentAccent | null;
  starter_questions: string[];
  /** Each null field inherits config.yaml. */
  llm: { provider: LlmProvider | null; model: string | null; temperature: number | null };
  /** null = built-in search chain. */
  pipeline_id: number | null;
  top_k: number | null;
  max_iterations: number | null;
  default_retrieval_mode: RetrievalMode;
  /** Other agents this one may consult as tools. */
  delegates: number[];
  routes: Record<AgentRouteName, AgentRouteConfig>;
}

/** One agent as the landing page and the rest of the app see it. */
export interface AgentCard extends ServiceWithRole {
  agent_config: AgentConfig;
  document_count: number;
  /** Resolved "provider · model" after config.yaml defaults apply. */
  model_label: string;
}

export interface ProviderInfo {
  provider: LlmProvider;
  available: boolean;
  reason: string | null;
  models: string[];
}

export interface ServiceMember {
  user_id: number;
  service_id: number;
  role: ServiceRole;
  created_at: string;
  updated_at: string;
}

export interface DocumentSummary {
  id: number;
  service_id: number;
  title: string;
  description: string | null;
  source_filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  status: DocumentStatus;
  error: string | null;
  chunk_config: ChunkConfig | null;
  embedding_model: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: DocumentSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface SearchHit {
  document_id: number;
  document_title: string | null;
  ordinal: number;
  score: number;
  text: string;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
}

// ---------------------------------------------------------------------------
// Pipeline types
// ---------------------------------------------------------------------------

export interface PipelineNodePosition {
  x: number;
  y: number;
}

export interface PipelineNodeData {
  config: Record<string, unknown>;
}

export interface PipelineNode {
  id: string;
  type: string;
  position: PipelineNodePosition;
  data: PipelineNodeData;
}

export interface PipelineEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle: string;
  targetHandle: string;
}

export interface PipelineGraph {
  nodes: PipelineNode[];
  edges: PipelineEdge[];
}

export type PipelineStatus = "draft" | "active" | "archived";

export interface Pipeline {
  id: number;
  service_id: number;
  name: string;
  status: PipelineStatus;
  graph_json: PipelineGraph;
  created_at: string;
  updated_at: string;
}

export interface PipelineReadiness {
  ready: boolean;
  components: Partial<Record<"embedder" | "reranker", boolean>>;
}

export interface PipelineRunRequest {
  query: string;
  top_k?: number;
}

export interface PipelineRunResponse {
  pipeline_id: number;
  query: string;
  results: SearchHit[];
  node_timings: Record<string, number>;
}

export interface HandleDef {
  name: string;
  handle_type: string;
}

export interface NodeSchemaEntry {
  label: string;
  description: string;
  inputs: HandleDef[];
  outputs: HandleDef[];
  config_schema: Record<string, unknown>;
}

export type PipelineSchema = Record<string, NodeSchemaEntry>;

// node_type → provider → model list
export type NodeModels = Record<string, Record<string, string[]>>;

// ---------------------------------------------------------------------------
// System prompts
// ---------------------------------------------------------------------------

export interface SystemPrompt {
  id: number;
  service_id: number;
  name: string;
  content: string;
  is_active: boolean;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Chat sessions
// ---------------------------------------------------------------------------

export interface ChatSession {
  id: number;
  service_id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionMessage {
  role: string;
  content: string;
  sources: SourceItem[];
}

// ---------------------------------------------------------------------------
// Chat / agent SSE
// ---------------------------------------------------------------------------

export type ChatRole = "user" | "assistant" | "system";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface SourceItem {
  index: number;
  document_id: number;
  title: string | null;
  snippet: string;
  score: number;
}

export interface AgentStep {
  type: "tool_call" | "observation";
  /** Tool name, or the agent's name when `delegate` is set. */
  tool: string;
  /** A call to another agent (agent-as-tool) rather than a document search. */
  delegate?: boolean;
  input?: string;
  output?: SourceItem[];
}

export type AgentRouteType = "retrieval" | "summary" | "comparison";
export type RetrievalMode = "on" | "off" | "auto";

/** Shape of the agent graph for one run, sent by the server before it executes. */
export interface GraphNode {
  id: string;
  label: string;
  kind: "entry" | "exit" | "supervisor" | "agent" | "delegate";
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string | null;
  conditional?: boolean;
  /** The source may call the target (a delegate agent) as a tool. */
  tool?: boolean;
}

export interface GraphTopology {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type NodeStatus = "running" | "done";

/** One timed unit of a run — a graph node, LLM call or tool call. */
export interface TraceSpan {
  id: string;
  parent_id: string | null;
  kind: "node" | "llm" | "tool";
  name: string;
  /** ms since the run started */
  start: number;
  end?: number;
  meta: Record<string, unknown>;
}

/** Progress inside a delegate agent: its node id → (inner node → status). */
export type DelegateStates = Record<string, Record<string, NodeStatus>>;

export interface ChatTurn {
  id: string;
  role: ChatRole;
  content: string;
  agentSteps: AgentStep[];
  sources: SourceItem[];
  isStreaming: boolean;
  agentRoute?: AgentRouteType;
  error?: string;
}
