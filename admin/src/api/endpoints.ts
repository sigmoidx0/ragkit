import { apiFetch, apiFetchBlob, apiSSE } from "./client";
import type {
  AgentCard,
  McpServer,
  McpServerInput,
  McpToolCall,
  Feedback,
  FeedbackOverview,
  RouteResult,
  UnansweredOverview,
  Rating,
  EvalCase,
  EvalRun,
  AgentConfig,
  ProviderInfo,
  ChatMessage,
  ChatSession,
  RetrievalMode,
  ChunkPreviewResponse,
  DocumentListResponse,
  DocumentSummary,
  NodeModels,
  Pipeline,
  PipelineGraph,
  PipelineReadiness,
  PipelineRunRequest,
  PipelineRunResponse,
  PipelineSchema,
  PipelineStatus,
  SearchResponse,
  Workspace,
  WorkspaceMember,
  WorkspaceWithRole,
  AgentSummary,
  DocumentSet,
  GraphPreview,
  SessionMessage,
  SystemPrompt,
  TokenResponse,
  User,
} from "./types";

export const AuthApi = {
  login: (email: string, password: string) =>
    apiFetch<TokenResponse>("/auth/login", { body: { email, password } }),
  me: () => apiFetch<User>("/auth/me"),
};

export const WorkspacesApi = {
  listMine: () => apiFetch<WorkspaceWithRole[]>("/me/workspaces"),
  listAll: () => apiFetch<Workspace[]>("/workspaces"),
  create: (name: string, slug: string) =>
    apiFetch<Workspace>("/workspaces", { body: { name, slug } }),
  remove: (workspaceId: number) =>
    apiFetch<void>(`/workspaces/${workspaceId}`, { method: "DELETE" }),
  listMembers: (workspaceId: number) =>
    apiFetch<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`),
  addMember: (workspaceId: number, userId: number, role: string) =>
    apiFetch<WorkspaceMember>(`/workspaces/${workspaceId}/members`, {
      body: { user_id: userId, role },
    }),
  updateMember: (workspaceId: number, userId: number, role: string) =>
    apiFetch<WorkspaceMember>(`/workspaces/${workspaceId}/members/${userId}`, {
      method: "PATCH",
      body: { role },
    }),
  removeMember: (workspaceId: number, userId: number) =>
    apiFetch<void>(`/workspaces/${workspaceId}/members/${userId}`, { method: "DELETE" }),
};

export const DocumentsApi = {
  list: (workspaceId: number, params: { limit?: number; offset?: number; q?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.limit != null) qs.set("limit", String(params.limit));
    if (params.offset != null) qs.set("offset", String(params.offset));
    if (params.q) qs.set("q", params.q);
    const suffix = qs.toString() ? `?${qs}` : "";
    return apiFetch<DocumentListResponse>(`/workspaces/${workspaceId}/documents${suffix}`);
  },
  get: (workspaceId: number, id: number) =>
    apiFetch<DocumentSummary>(`/workspaces/${workspaceId}/documents/${id}`),
  create: (workspaceId: number, fd: FormData) =>
    apiFetch<DocumentSummary>(`/workspaces/${workspaceId}/documents`, { formData: fd }),
  update: (workspaceId: number, id: number, body: { title?: string; description?: string }) =>
    apiFetch<DocumentSummary>(`/workspaces/${workspaceId}/documents/${id}`, { method: "PATCH", body }),
  remove: (workspaceId: number, id: number) =>
    apiFetch<void>(`/workspaces/${workspaceId}/documents/${id}`, { method: "DELETE" }),
  fetchFile: (workspaceId: number, id: number) =>
    apiFetchBlob(`/workspaces/${workspaceId}/documents/${id}/file`),
  previewText: (workspaceId: number, id: number) =>
    apiFetch<{ text: string }>(`/workspaces/${workspaceId}/documents/${id}/preview-text`),
};

export const IngestApi = {
  previewChunks: (fd: FormData) =>
    apiFetch<ChunkPreviewResponse>("/ingest/preview-chunks", { formData: fd }),
};

export const UsersApi = {
  list: () => apiFetch<User[]>("/users"),
  create: (email: string, password: string) =>
    apiFetch<User>("/users", { body: { email, password } }),
};

export const SearchApi = {
  run: (
    workspaceId: number,
    payload: {
      query: string;
      top_k?: number;
      document_id?: number | null;
      pipeline_id?: number | null;
      /** Limit to documents in these sets — an agent's retrieval scope. */
      document_set_ids?: number[] | null;
    },
  ) =>
    apiFetch<SearchResponse>(`/workspaces/${workspaceId}/search`, { body: payload }),
};

export const AgentsApi = {
  /** Agent cards the user can reach; pass a workspace to list just its agents. */
  listMine: (workspaceId?: number) =>
    apiFetch<AgentCard[]>(`/me/agents${workspaceId != null ? `?workspace_id=${workspaceId}` : ""}`),
  create: (workspaceId: number, name: string, copyFromAgentId?: number | null) =>
    apiFetch<AgentSummary>(`/workspaces/${workspaceId}/agents`, {
      body: { name, copy_from_agent_id: copyFromAgentId ?? null },
    }),
  rename: (agentId: number, name: string) =>
    apiFetch<AgentSummary>(`/agents/${agentId}`, { method: "PATCH", body: { name } }),
  remove: (agentId: number) => apiFetch<void>(`/agents/${agentId}`, { method: "DELETE" }),
  getConfig: (agentId: number) => apiFetch<AgentConfig>(`/agents/${agentId}/config`),
  updateConfig: (agentId: number, config: AgentConfig) =>
    apiFetch<AgentConfig>(`/agents/${agentId}/config`, { method: "PUT", body: config }),
  previewGraph: (agentId: number, config: AgentConfig, retrievalMode?: RetrievalMode) =>
    apiFetch<GraphPreview>(`/agents/${agentId}/graph-preview`, {
      body: { config, retrieval_mode: retrievalMode ?? null },
    }),
  providers: () => apiFetch<ProviderInfo[]>("/llm/providers"),
  /** Which of the workspace's agents should take this question. */
  route: (workspaceId: number, question: string) =>
    apiFetch<RouteResult>(`/workspaces/${workspaceId}/route`, { body: { question } }),
};

export const EvalsApi = {
  list: (agentId: number) => apiFetch<EvalRun[]>(`/agents/${agentId}/evals`),
  create: (
    agentId: number,
    body: { name: string; cases: EvalCase[]; config?: AgentConfig | null; system_prompt_id?: number | null },
  ) =>
    apiFetch<EvalRun>(`/agents/${agentId}/evals`, { body }),
  remove: (agentId: number, runId: number) =>
    apiFetch<void>(`/agents/${agentId}/evals/${runId}`, { method: "DELETE" }),
};

export const FeedbackApi = {
  list: (agentId: number, rating?: Rating) =>
    apiFetch<FeedbackOverview>(`/agents/${agentId}/feedback${rating ? `?rating=${rating}` : ""}`),
  unanswered: (agentId: number) => apiFetch<UnansweredOverview>(`/agents/${agentId}/unanswered`),
};

export const DocumentSetsApi = {
  list: (workspaceId: number) => apiFetch<DocumentSet[]>(`/workspaces/${workspaceId}/document-sets`),
  create: (workspaceId: number, body: { name: string; description?: string | null; document_ids?: number[] }) =>
    apiFetch<DocumentSet>(`/workspaces/${workspaceId}/document-sets`, { body }),
  update: (
    workspaceId: number,
    setId: number,
    body: { name?: string; description?: string | null; document_ids?: number[] },
  ) => apiFetch<DocumentSet>(`/workspaces/${workspaceId}/document-sets/${setId}`, { method: "PATCH", body }),
  remove: (workspaceId: number, setId: number) =>
    apiFetch<void>(`/workspaces/${workspaceId}/document-sets/${setId}`, { method: "DELETE" }),
};

export const PipelineApi = {
  schema: () => apiFetch<PipelineSchema>("/pipeline-schema"),
  nodeModels: () => apiFetch<NodeModels>("/pipeline-node-models"),
  defaultGraph: () => apiFetch<PipelineGraph>("/pipeline-default"),
  list: (workspaceId: number) =>
    apiFetch<Pipeline[]>(`/workspaces/${workspaceId}/pipelines`),
  get: (workspaceId: number, pipelineId: number) =>
    apiFetch<Pipeline>(`/workspaces/${workspaceId}/pipelines/${pipelineId}`),
  create: (workspaceId: number, body: { name: string; graph_json: PipelineGraph }) =>
    apiFetch<Pipeline>(`/workspaces/${workspaceId}/pipelines`, { body }),
  update: (workspaceId: number, pipelineId: number, body: { name?: string; graph_json?: PipelineGraph }) =>
    apiFetch<Pipeline>(`/workspaces/${workspaceId}/pipelines/${pipelineId}`, { method: "PUT", body }),
  remove: (workspaceId: number, pipelineId: number) =>
    apiFetch<void>(`/workspaces/${workspaceId}/pipelines/${pipelineId}`, { method: "DELETE" }),
  setStatus: (workspaceId: number, pipelineId: number, status: PipelineStatus) =>
    apiFetch<Pipeline>(`/workspaces/${workspaceId}/pipelines/${pipelineId}/status`, { method: "PATCH", body: { status } }),
  readiness: (workspaceId: number, pipelineId: number) =>
    apiFetch<PipelineReadiness>(`/workspaces/${workspaceId}/pipelines/${pipelineId}/readiness`),
  prepare: (workspaceId: number, pipelineId: number) =>
    apiFetch<{ ready: true }>(`/workspaces/${workspaceId}/pipelines/${pipelineId}/prepare`, { body: {} }),
  run: (workspaceId: number, pipelineId: number, body: PipelineRunRequest) =>
    apiFetch<PipelineRunResponse>(`/workspaces/${workspaceId}/pipelines/${pipelineId}/run`, { body }),
};

export const SystemPromptsApi = {
  list: (agentId: number) =>
    apiFetch<SystemPrompt[]>(`/agents/${agentId}/system-prompts`),
  create: (agentId: number, body: { name: string; content: string }) =>
    apiFetch<SystemPrompt>(`/agents/${agentId}/system-prompts`, { body }),
  update: (agentId: number, id: number, body: { name?: string; content?: string }) =>
    apiFetch<SystemPrompt>(`/agents/${agentId}/system-prompts/${id}`, { method: "PATCH", body }),
  activate: (agentId: number, id: number) =>
    apiFetch<SystemPrompt>(`/agents/${agentId}/system-prompts/${id}/activate`, { body: {} }),
  remove: (agentId: number, id: number) =>
    apiFetch<void>(`/agents/${agentId}/system-prompts/${id}`, { method: "DELETE" }),
};

export const ChatApi = {
  stream: (agentId: number, messages: ChatMessage[], topK?: number, signal?: AbortSignal) =>
    apiSSE(`/agents/${agentId}/chat`, { messages, top_k: topK }, signal),
};

export const SessionsApi = {
  list: (agentId: number) =>
    apiFetch<ChatSession[]>(`/agents/${agentId}/sessions`),
  create: (agentId: number, title?: string | null) =>
    apiFetch<ChatSession>(`/agents/${agentId}/sessions`, { body: { title: title ?? null } }),
  messages: (agentId: number, sessionId: number) =>
    apiFetch<SessionMessage[]>(`/agents/${agentId}/sessions/${sessionId}/messages`),
  rate: (agentId: number, sessionId: number, turnIndex: number, rating: Rating, comment?: string | null) =>
    apiFetch<Feedback>(`/agents/${agentId}/sessions/${sessionId}/turns/${turnIndex}/feedback`, {
      method: "PUT",
      body: { rating, comment: comment ?? null },
    }),
  clearRating: (agentId: number, sessionId: number, turnIndex: number) =>
    apiFetch<void>(`/agents/${agentId}/sessions/${sessionId}/turns/${turnIndex}/feedback`, { method: "DELETE" }),
  remove: (agentId: number, sessionId: number) =>
    apiFetch<void>(`/agents/${agentId}/sessions/${sessionId}`, { method: "DELETE" }),
  pendingApprovals: (agentId: number, sessionId: number) =>
    apiFetch<{ id: number; server_name: string; tool: string; args: Record<string, unknown> }[]>(
      `/agents/${agentId}/sessions/${sessionId}/approvals`,
    ),
  /** Approve or reject pending MCP calls; streams the rest of the paused turn. */
  decide: (
    agentId: number,
    sessionId: number,
    decisions: { call_id: number; approve: boolean; args?: Record<string, unknown> | null }[],
    signal?: AbortSignal,
  ) => apiSSE(`/agents/${agentId}/sessions/${sessionId}/approvals`, { decisions }, signal),
  /**
   * `replaceTurn` (0-based, counting user messages) reruns from that message: edit or
   * regenerate. `regenerate` answers at a modestly higher temperature so the answer can differ.
   */
  chat: (
    agentId: number,
    sessionId: number,
    message: string,
    topK?: number,
    signal?: AbortSignal,
    retrievalMode?: RetrievalMode,
    replaceTurn?: number,
    regenerate?: boolean,
  ) =>
    apiSSE(
      `/agents/${agentId}/sessions/${sessionId}/chat`,
      {
        message,
        top_k: topK,
        retrieval_mode: retrievalMode ?? null,
        replace_turn: replaceTurn ?? null,
        regenerate: regenerate ?? false,
      },
      signal,
    ),
};

export const McpApi = {
  list: (workspaceId: number) => apiFetch<McpServer[]>(`/workspaces/${workspaceId}/mcp-servers`),
  create: (workspaceId: number, body: McpServerInput) =>
    apiFetch<McpServer>(`/workspaces/${workspaceId}/mcp-servers`, { body }),
  update: (workspaceId: number, serverId: number, body: McpServerInput) =>
    apiFetch<McpServer>(`/workspaces/${workspaceId}/mcp-servers/${serverId}`, { method: "PATCH", body }),
  refresh: (workspaceId: number, serverId: number) =>
    apiFetch<McpServer>(`/workspaces/${workspaceId}/mcp-servers/${serverId}/refresh`, { method: "POST" }),
  remove: (workspaceId: number, serverId: number) =>
    apiFetch<void>(`/workspaces/${workspaceId}/mcp-servers/${serverId}`, { method: "DELETE" }),
  calls: (workspaceId: number, limit = 50) =>
    apiFetch<McpToolCall[]>(`/workspaces/${workspaceId}/mcp-calls?limit=${limit}`),
};
