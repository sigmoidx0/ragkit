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
  id: number;
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
