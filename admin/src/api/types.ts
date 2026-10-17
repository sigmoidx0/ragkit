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

export type WorkspaceRole = "admin" | "member" | "viewer";

/** The tenant: members, documents, document sets and pipelines live here. */
export interface Workspace {
  id: number;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceWithRole extends Workspace {
  role: WorkspaceRole;
}

/** A named group of a workspace's documents; agents choose which sets to search. */
export interface DocumentSet {
  id: number;
  workspace_id: number;
  name: string;
  description: string | null;
  document_ids: number[];
  /** Agents in the workspace that search this set. */
  used_by: { id: number; name: string }[];
  created_at: string;
  updated_at: string;
}

// ── Agents ────────────────────────────────────────────────────────────────────

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
  /** Document sets to search; empty = every document in the workspace. */
  document_set_ids: number[];
  /** null = built-in search chain. */
  pipeline_id: number | null;
  top_k: number | null;
  max_iterations: number | null;
  default_retrieval_mode: RetrievalMode;
  /** Other agents this one may consult as tools. */
  delegates: number[];
  /** Tools from the workspace's MCP servers; "required" pauses for the user's approval. */
  mcp_tools: McpToolRef[];
  routes: Record<AgentRouteName, AgentRouteConfig>;
}

/** One agent as the landing page and the rest of the app see it. */
export interface AgentSummary {
  id: number;
  workspace_id: number;
  name: string;
  created_at: string;
  updated_at: string;
}

/** One agent as the landing page and the rest of the app see it. */
export interface AgentCard extends AgentSummary {
  workspace_name: string;
  /** The user's role in the agent's workspace. */
  role: WorkspaceRole;
  agent_config: AgentConfig;
  /** Documents the agent can search (its document sets, or the whole workspace). */
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

export interface WorkspaceMember {
  user_id: number;
  workspace_id: number;
  role: WorkspaceRole;
  created_at: string;
  updated_at: string;
}

export interface DocumentSummary {
  id: number;
  workspace_id: number;
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
  workspace_id: number;
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
  agent_id: number;
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
  agent_id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export type Rating = 1 | -1;

export interface Feedback {
  rating: Rating;
  comment: string | null;
}

export interface SessionMessage {
  role: string;
  content: string;
  sources: SourceItem[];
  /** Assistant messages: which answer in the session this is (0-based). */
  turn_index: number | null;
  feedback: Feedback | null;
}

export interface FeedbackItem {
  id: number;
  session_id: number;
  session_title: string | null;
  user_email: string;
  turn_index: number;
  rating: Rating;
  comment: string | null;
  question: string;
  /** The standalone rewrite of `question`, when the turn was logged. */
  query: string | null;
  answer: string;
  created_at: string;
}

export interface FeedbackOverview {
  up: number;
  down: number;
  items: FeedbackItem[];
}

/** A question the agent searched for but answered without citing anything. */
export interface UnansweredItem {
  session_id: number;
  session_title: string | null;
  user_email: string;
  turn_index: number;
  question: string;
  query: string;
  route: string | null;
  source_count: number;
  created_at: string;
}

export interface UnansweredOverview {
  /** Logged turns that searched, and how many of those cited nothing. */
  searched: number;
  unanswered: number;
  items: UnansweredItem[];
}

export interface RouteResult {
  agent_id: number;
  /** One sentence on why; empty when the workspace has a single agent. */
  reason: string;
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
  kind: "entry" | "exit" | "supervisor" | "agent" | "delegate" | "step" | "mcp";
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

/** Settings preview: the draft's graph, plus how many documents its sets cover. */
export interface GraphPreview extends GraphTopology {
  /** null = no sets selected, i.e. the whole workspace. */
  document_count: number | null;
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

// ── MCP ──────────────────────────────────────────────────────────────────────

export type McpApproval = "auto" | "required";

export interface McpToolRef {
  server_id: number;
  tool: string;
  approval: McpApproval;
}

export interface McpToolSpec {
  name: string;
  title: string | null;
  description: string;
  input_schema: Record<string, unknown>;
  read_only: boolean;
  destructive: boolean;
}

export interface McpServer {
  id: number;
  workspace_id: number;
  name: string;
  description: string | null;
  url: string;
  auth_env_var: string | null;
  /** Whether that variable is set on the ragkit server (never its value). */
  auth_configured: boolean;
  enabled: boolean;
  tools: McpToolSpec[];
  tools_refreshed_at: string | null;
  last_error: string | null;
  used_by: { id: number; name: string }[];
}

export interface McpServerInput {
  name?: string;
  url?: string;
  description?: string | null;
  auth_env_var?: string | null;
  enabled?: boolean;
}

export type McpCallStatus = "auto" | "pending" | "approved" | "rejected" | "expired";

export interface McpToolCall {
  id: number;
  agent_id: number;
  agent_name: string;
  session_id: number | null;
  server_name: string;
  tool: string;
  args: Record<string, unknown>;
  approved_args: Record<string, unknown> | null;
  status: McpCallStatus;
  requested_by: string | null;
  decided_by: string | null;
  decided_at: string | null;
  result: string | null;
  is_error: boolean;
  created_at: string;
}

/** An MCP call made during a chat turn, as streamed. */
export interface McpAction {
  id: string;
  server: string;
  tool: string;
  args: Record<string, unknown>;
  status: "running" | "waiting" | "done" | "error";
  output?: string | null;
}

/** A call the paused run waits on. */
export interface PendingApproval {
  call_id: number;
  server: string;
  tool: string;
  title?: string | null;
  args: Record<string, unknown>;
}

export interface ChatTurn {
  id: string;
  role: ChatRole;
  content: string;
  agentSteps: AgentStep[];
  sources: SourceItem[];
  isStreaming: boolean;
  agentRoute?: AgentRouteType;
  error?: string;
  /** Assistant turns: position among the session's answers, for rating it. */
  turnIndex?: number;
  feedback?: Feedback | null;
  /** MCP tool calls in this turn. */
  actions?: McpAction[];
  /** Calls waiting for the user's approval; the turn continues once decided. */
  approvals?: PendingApproval[];
}

// ── Evaluations ───────────────────────────────────────────────────────────────

export interface EvalCase {
  question: string;
  /** The document a good answer should come from (enables hit / MRR). */
  expected_document_id: number | null;
  /** Facts a correct answer must state (enables answer coverage). */
  expected_keywords?: string[];
}

export interface EvalCaseResult {
  question: string;
  expected_document_id: number | null;
  answer: string;
  route: string | null;
  sources: SourceItem[];
  latency_ms: number;
  tool_calls: number;
  input_tokens: number;
  output_tokens: number;
  hit: boolean | null;
  rank: number | null;
  keyword_recall: number | null;
  missing_keywords: string[];
  groundedness: number | null;
  judge_reason: string | null;
  error: string | null;
}

export interface EvalSummary {
  cases: number;
  completed: number;
  errors: number;
  hit_rate: number | null;
  mrr: number | null;
  keyword_recall: number | null;
  avg_groundedness: number | null;
  avg_latency_ms: number | null;
  p95_latency_ms: number | null;
  avg_tool_calls: number | null;
  total_tokens: number;
  judge_model: string;
}

export type EvalStatus = "pending" | "running" | "done" | "failed";

export interface EvalRun {
  id: number;
  agent_id: number;
  name: string;
  status: EvalStatus;
  config_snapshot: AgentConfig;
  /** The system prompt the run used (snapshotted when it was created). */
  prompt_name: string | null;
  cases: EvalCase[];
  results: EvalCaseResult[];
  summary: EvalSummary | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}
