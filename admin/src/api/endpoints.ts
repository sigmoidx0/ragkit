import { apiFetch } from "./client";
import type {
  DocumentListResponse,
  DocumentSummary,
  SearchResponse,
  Service,
  ServiceMember,
  ServiceWithRole,
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
  replace: (serviceId: number, id: number, fd: FormData) =>
    apiFetch<DocumentSummary>(`/services/${serviceId}/documents/${id}/replace`, { formData: fd }),
  remove: (serviceId: number, id: number) =>
    apiFetch<void>(`/services/${serviceId}/documents/${id}`, { method: "DELETE" }),
  fileUrl: (serviceId: number, id: number) => `/api/services/${serviceId}/documents/${id}/file`,
  previewText: (serviceId: number, id: number) =>
    apiFetch<{ text: string }>(`/services/${serviceId}/documents/${id}/preview-text`),
};

export const UsersApi = {
  list: () => apiFetch<User[]>("/users"),
  create: (email: string, password: string) =>
    apiFetch<User>("/users", { body: { email, password } }),
};

export const SearchApi = {
  run: (serviceId: number, payload: { query: string; top_k?: number; document_id?: number | null }) =>
    apiFetch<SearchResponse>(`/services/${serviceId}/search`, { body: payload }),
};
