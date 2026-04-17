import { apiFetch } from "./client";
import type { DocumentListResponse, DocumentSummary, SearchResponse, TokenResponse, User } from "./types";

export const AuthApi = {
  login: (email: string, password: string) =>
    apiFetch<TokenResponse>("/auth/login", { body: { email, password } }),
  me: () => apiFetch<User>("/auth/me"),
};

export const DocumentsApi = {
  list: (params: { limit?: number; offset?: number; q?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.limit != null) qs.set("limit", String(params.limit));
    if (params.offset != null) qs.set("offset", String(params.offset));
    if (params.q) qs.set("q", params.q);
    const suffix = qs.toString() ? `?${qs}` : "";
    return apiFetch<DocumentListResponse>(`/documents${suffix}`);
  },
  get: (id: number) => apiFetch<DocumentSummary>(`/documents/${id}`),
  create: (fd: FormData) => apiFetch<DocumentSummary>("/documents", { formData: fd }),
  replace: (id: number, fd: FormData) =>
    apiFetch<DocumentSummary>(`/documents/${id}/replace`, { formData: fd }),
  remove: (id: number) => apiFetch<void>(`/documents/${id}`, { method: "DELETE" }),
  fileUrl: (id: number) => `/api/documents/${id}/file`,
};

export const SearchApi = {
  run: (payload: { query: string; top_k?: number; document_id?: number | null }) =>
    apiFetch<SearchResponse>("/search", { body: payload }),
};
