import { apiFetch, apiFetchBlob, apiSSE } from "./client";
import type {
  ChatMessage,
  ChatSession,
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
  Service,
  ServiceMember,
  ServiceWithRole,
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

export const ServicesApi = {
  listMine: () => apiFetch<ServiceWithRole[]>("/me/services"),
  listAll: () => apiFetch<Service[]>("/services"),
  create: (name: string, slug: string) =>
    apiFetch<Service>("/services", { body: { name, slug } }),
  remove: (serviceId: number) =>
    apiFetch<void>(`/services/${serviceId}`, { method: "DELETE" }),
  listMembers: (serviceId: number) =>
    apiFetch<ServiceMember[]>(`/services/${serviceId}/members`),
  addMember: (serviceId: number, userId: number, role: string) =>
    apiFetch<ServiceMember>(`/services/${serviceId}/members`, {
      body: { user_id: userId, role },
    }),
  updateMember: (serviceId: number, userId: number, role: string) =>
    apiFetch<ServiceMember>(`/services/${serviceId}/members/${userId}`, {
      method: "PATCH",
      body: { role },
    }),
  removeMember: (serviceId: number, userId: number) =>
    apiFetch<void>(`/services/${serviceId}/members/${userId}`, { method: "DELETE" }),
};

export const DocumentsApi = {
  list: (serviceId: number, params: { limit?: number; offset?: number; q?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.limit != null) qs.set("limit", String(params.limit));
    if (params.offset != null) qs.set("offset", String(params.offset));
    if (params.q) qs.set("q", params.q);
    const suffix = qs.toString() ? `?${qs}` : "";
    return apiFetch<DocumentListResponse>(`/services/${serviceId}/documents${suffix}`);
  },
  get: (serviceId: number, id: number) =>
    apiFetch<DocumentSummary>(`/services/${serviceId}/documents/${id}`),
  create: (serviceId: number, fd: FormData) =>
    apiFetch<DocumentSummary>(`/services/${serviceId}/documents`, { formData: fd }),
  update: (serviceId: number, id: number, body: { title?: string; description?: string }) =>
    apiFetch<DocumentSummary>(`/services/${serviceId}/documents/${id}`, { method: "PATCH", body }),
  remove: (serviceId: number, id: number) =>
    apiFetch<void>(`/services/${serviceId}/documents/${id}`, { method: "DELETE" }),
  fetchFile: (serviceId: number, id: number) =>
    apiFetchBlob(`/services/${serviceId}/documents/${id}/file`),
  previewText: (serviceId: number, id: number) =>
    apiFetch<{ text: string }>(`/services/${serviceId}/documents/${id}/preview-text`),
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
  run: (serviceId: number, payload: { query: string; top_k?: number; document_id?: number | null; pipeline_id?: number | null }) =>
    apiFetch<SearchResponse>(`/services/${serviceId}/search`, { body: payload }),
};

export const PipelineApi = {
  schema: () => apiFetch<PipelineSchema>("/pipeline-schema"),
  nodeModels: () => apiFetch<NodeModels>("/pipeline-node-models"),
  list: (serviceId: number) =>
    apiFetch<Pipeline[]>(`/services/${serviceId}/pipelines`),
  get: (serviceId: number, pipelineId: number) =>
    apiFetch<Pipeline>(`/services/${serviceId}/pipelines/${pipelineId}`),
  create: (serviceId: number, body: { name: string; graph_json: PipelineGraph }) =>
    apiFetch<Pipeline>(`/services/${serviceId}/pipelines`, { body }),
  update: (serviceId: number, pipelineId: number, body: { name?: string; graph_json?: PipelineGraph }) =>
    apiFetch<Pipeline>(`/services/${serviceId}/pipelines/${pipelineId}`, { method: "PUT", body }),
  remove: (serviceId: number, pipelineId: number) =>
    apiFetch<void>(`/services/${serviceId}/pipelines/${pipelineId}`, { method: "DELETE" }),
  setStatus: (serviceId: number, pipelineId: number, status: PipelineStatus) =>
    apiFetch<Pipeline>(`/services/${serviceId}/pipelines/${pipelineId}/status`, { method: "PATCH", body: { status } }),
  readiness: (serviceId: number, pipelineId: number) =>
    apiFetch<PipelineReadiness>(`/services/${serviceId}/pipelines/${pipelineId}/readiness`),
  prepare: (serviceId: number, pipelineId: number) =>
    apiFetch<{ ready: true }>(`/services/${serviceId}/pipelines/${pipelineId}/prepare`, { body: {} }),
  run: (serviceId: number, pipelineId: number, body: PipelineRunRequest) =>
    apiFetch<PipelineRunResponse>(`/services/${serviceId}/pipelines/${pipelineId}/run`, { body }),
};

export const SystemPromptsApi = {
  list: (serviceId: number) =>
    apiFetch<SystemPrompt[]>(`/services/${serviceId}/system-prompts`),
  create: (serviceId: number, body: { name: string; content: string }) =>
    apiFetch<SystemPrompt>(`/services/${serviceId}/system-prompts`, { body }),
  update: (serviceId: number, id: number, body: { name?: string; content?: string }) =>
    apiFetch<SystemPrompt>(`/services/${serviceId}/system-prompts/${id}`, { method: "PATCH", body }),
  activate: (serviceId: number, id: number) =>
    apiFetch<SystemPrompt>(`/services/${serviceId}/system-prompts/${id}/activate`, { body: {} }),
  remove: (serviceId: number, id: number) =>
    apiFetch<void>(`/services/${serviceId}/system-prompts/${id}`, { method: "DELETE" }),
};

export const ChatApi = {
  stream: (serviceId: number, messages: ChatMessage[], topK?: number, signal?: AbortSignal) =>
    apiSSE(`/services/${serviceId}/chat`, { messages, top_k: topK }, signal),
};

export const SessionsApi = {
  list: (serviceId: number) =>
    apiFetch<ChatSession[]>(`/services/${serviceId}/sessions`),
  create: (serviceId: number, title?: string | null) =>
    apiFetch<ChatSession>(`/services/${serviceId}/sessions`, { body: { title: title ?? null } }),
  messages: (serviceId: number, sessionId: number) =>
    apiFetch<SessionMessage[]>(`/services/${serviceId}/sessions/${sessionId}/messages`),
  remove: (serviceId: number, sessionId: number) =>
    apiFetch<void>(`/services/${serviceId}/sessions/${sessionId}`, { method: "DELETE" }),
  chat: (serviceId: number, sessionId: number, message: string, topK?: number, signal?: AbortSignal) =>
    apiSSE(`/services/${serviceId}/sessions/${sessionId}/chat`, { message, top_k: topK }, signal),
};
