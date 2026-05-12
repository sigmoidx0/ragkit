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
  tool: string;
  input?: string;
  output?: SourceItem[];
}

export interface ChatTurn {
  id: string;
  role: ChatRole;
  content: string;
  agentSteps: AgentStep[];
  sources: SourceItem[];
  isStreaming: boolean;
  error?: string;
}
