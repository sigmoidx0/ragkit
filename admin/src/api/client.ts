const TOKEN_KEY = "ragkit.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (opts.formData) {
    body = opts.formData;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const resp = await fetch(`/api${path}`, {
    method: opts.method ?? (body ? "POST" : "GET"),
    headers,
    body,
    signal: opts.signal,
  });

  if (resp.status === 204) {
    return undefined as T;
  }

  const text = await resp.text();
  let json: unknown = null;
  if (text) {
    try {
      json = JSON.parse(text);
    } catch {
      json = text;
    }
  }

  if (!resp.ok) {
    const detail =
      (json && typeof json === "object" && "detail" in json
        ? (json as { detail: unknown }).detail
        : null) ?? resp.statusText;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail);
    if (resp.status === 401) {
      setToken(null);
    }
    throw new ApiError(resp.status, message, detail);
  }
  return json as T;
}

export interface SSEEvent {
  event: string;
  data: string;
}

export async function* apiSSE(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const token = getToken();
  const resp = await fetch(`/api${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!resp.ok) {
    if (resp.status === 401) setToken(null);
    const text = await resp.text();
    throw new ApiError(resp.status, text);
  }

  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        yield { event: currentEvent, data: line.slice(6) };
        currentEvent = "message";
      } else if (line === "") {
        currentEvent = "message";
      }
    }
  }
}

export async function apiFetchBlob(path: string): Promise<{ blob: Blob; filename?: string }> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(`/api${path}`, { headers });

  if (!resp.ok) {
    if (resp.status === 401) setToken(null);
    throw new ApiError(resp.status, resp.statusText);
  }

  const disposition = resp.headers.get("content-disposition");
  const filename = disposition?.match(/filename="?([^"]+)"?/)?.[1] ?? undefined;
  const blob = await resp.blob();
  return { blob, filename };
}
