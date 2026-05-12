import { useRef, useState, useEffect, type KeyboardEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SessionsApi, SystemPromptsApi } from "@/api/endpoints";
import { useService } from "@/services/ServiceProvider";
import { useAuth } from "@/auth/AuthProvider";
import { Button, Card, Textarea, Badge } from "@/components/ui";
import { cn } from "@/lib/cn";
import type { AgentStep, ChatRole, ChatSession, ChatTurn, SourceItem, SystemPrompt } from "@/api/types";

// ── Icons ────────────────────────────────────────────────────────────────────

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
    >
      <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5">
      <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
    </svg>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatSessionDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return date.toLocaleDateString([], { weekday: "long" });
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

// ── Agent steps ───────────────────────────────────────────────────────────────

function AgentSteps({ steps }: { steps: AgentStep[] }) {
  const [open, setOpen] = useState(false);
  if (steps.length === 0) return null;

  const toolCalls = steps.filter((s) => s.type === "tool_call");
  const totalSources = steps
    .filter((s) => s.type === "observation")
    .reduce((acc, s) => acc + (s.output?.length ?? 0), 0);

  return (
    <div className="mb-2 rounded-xl border border-gray-100 bg-gray-50 text-xs dark:border-gray-700 dark:bg-gray-700/40">
      <button
        onClick={() => setOpen((p) => !p)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
      >
        <ChevronIcon open={open} />
        <span>
          {toolCalls.length} search{toolCalls.length !== 1 ? "es" : ""} · {totalSources} source
          {totalSources !== 1 ? "s" : ""} found
        </span>
      </button>
      {open && (
        <div className="border-t border-gray-100 px-3 py-2 space-y-2 dark:border-gray-700">
          {steps.map((step, i) => (
            <div key={i} className="flex gap-2">
              {step.type === "tool_call" ? (
                <>
                  <span className="text-teal-500">🔍</span>
                  <span className="text-gray-600 dark:text-gray-300">
                    Searching: <span className="font-mono">{step.input}</span>
                  </span>
                </>
              ) : (
                <>
                  <span className="text-blue-400">📄</span>
                  <span className="text-gray-500 dark:text-gray-400">
                    Found {step.output?.length ?? 0} result{(step.output?.length ?? 0) !== 1 ? "s" : ""}
                  </span>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Sources ──────────────────────────────────────────────────────────────────

function Sources({ sources }: { sources: SourceItem[] }) {
  if (sources.length === 0) return null;
  const unique = sources.filter((s, i, arr) => arr.findIndex((x) => x.index === s.index) === i);
  return (
    <div className="mt-3 space-y-1">
      <p className="text-xs font-semibold text-gray-400 dark:text-gray-500">Sources</p>
      {unique.map((s) => (
        <div
          key={s.index}
          className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-1.5 text-xs dark:border-gray-700 dark:bg-gray-700/40"
        >
          <span className="mr-2 font-mono text-teal-500">[{s.index}]</span>
          <span className="font-medium text-gray-700 dark:text-gray-200">
            {s.title ?? `Document #${s.document_id}`}
          </span>
          <span className="ml-2 text-gray-400">score {s.score < 0.01 ? s.score.toExponential(2) : s.score.toFixed(3)}</span>
        </div>
      ))}
    </div>
  );
}

// ── Message bubble ───────────────────────────────────────────────────────────

function MessageBubble({ turn }: { turn: ChatTurn }) {
  const isUser = turn.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[80%]", isUser ? "order-2" : "order-1")}>
        {!isUser && <AgentSteps steps={turn.agentSteps} />}
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm",
            isUser
              ? "bg-teal-400 text-white"
              : "bg-white shadow-sm border border-gray-100 text-gray-800 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100",
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{turn.content}</p>
          ) : turn.isStreaming && !turn.content ? (
            <span className="inline-flex gap-1">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" />
            </span>
          ) : turn.error ? (
            <p className="text-red-500">{turn.error}</p>
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {turn.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
        {!isUser && <Sources sources={turn.sources} />}
      </div>
    </div>
  );
}

// ── Sessions sidebar ─────────────────────────────────────────────────────────

function SessionSidebar({
  sessions,
  activeId,
  onSelect,
  onDelete,
  onNew,
  creating,
  disabled,
}: {
  sessions: ChatSession[];
  activeId: number | null;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  onNew: () => void;
  creating: boolean;
  disabled: boolean;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="p-3 border-b border-gray-100 dark:border-gray-700">
        <Button
          size="sm"
          variant="secondary"
          className="w-full flex items-center justify-center gap-1.5"
          onClick={onNew}
          disabled={creating || disabled}
        >
          <PlusIcon />
          New Chat
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {sessions.length === 0 ? (
          <p className="py-6 text-center text-xs text-gray-400">No sessions yet</p>
        ) : (
          sessions.map((session) => (
            <div
              key={session.id}
              onClick={() => onSelect(session.id)}
              className={cn(
                "group flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-xs transition-colors",
                activeId === session.id
                  ? "bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300"
                  : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700/50",
              )}
            >
              <span className="flex-1 truncate">
                {session.title ?? formatSessionDate(session.updated_at)}
              </span>
              <button
                className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100 hover:text-red-500"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(session.id);
                }}
              >
                <TrashIcon />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ── System prompts panel ─────────────────────────────────────────────────────

function SystemPromptsPanel({
  serviceId,
  onClose,
  isAdmin,
}: {
  serviceId: number;
  onClose: () => void;
  isAdmin: boolean;
}) {
  const qc = useQueryClient();
  const [newName, setNewName] = useState("");
  const [newContent, setNewContent] = useState("");
  const [creating, setCreating] = useState(false);

  const { data: prompts = [], isLoading } = useQuery({
    queryKey: ["system-prompts", serviceId],
    queryFn: () => SystemPromptsApi.list(serviceId),
  });

  const activate = useMutation({
    mutationFn: (id: number) => SystemPromptsApi.activate(serviceId, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system-prompts", serviceId] });
      toast.success("System prompt activated");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed"),
  });

  const remove = useMutation({
    mutationFn: (id: number) => SystemPromptsApi.remove(serviceId, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system-prompts", serviceId] });
      toast.success("Deleted");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed"),
  });

  const create = useMutation({
    mutationFn: () => SystemPromptsApi.create(serviceId, { name: newName, content: newContent }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system-prompts", serviceId] });
      setNewName("");
      setNewContent("");
      setCreating(false);
      toast.success("Created");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3 dark:border-gray-700">
        <p className="text-sm font-semibold text-gray-700 dark:text-gray-200">System Prompts</p>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
          <CloseIcon />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {isLoading ? (
          <p className="text-xs text-gray-400">Loading…</p>
        ) : prompts.length === 0 ? (
          <p className="text-xs text-gray-400">No system prompts. The fallback from config will be used.</p>
        ) : (
          prompts.map((p) => (
            <PromptCard
              key={p.id}
              prompt={p}
              isAdmin={isAdmin}
              onActivate={() => activate.mutate(p.id)}
              onDelete={() => remove.mutate(p.id)}
            />
          ))
        )}
      </div>
      {isAdmin && (
        <div className="border-t border-gray-100 p-4 dark:border-gray-700">
          {creating ? (
            <div className="space-y-2">
              <input
                className="block w-full rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-xs dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
                placeholder="Name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <Textarea
                className="text-xs"
                rows={4}
                placeholder="System prompt content…"
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={() => create.mutate()}
                  disabled={!newName.trim() || !newContent.trim() || create.isPending}
                >
                  Save
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setCreating(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button size="sm" variant="secondary" className="w-full" onClick={() => setCreating(true)}>
              + New prompt
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function PromptCard({
  prompt,
  isAdmin,
  onActivate,
  onDelete,
}: {
  prompt: SystemPrompt;
  isAdmin: boolean;
  onActivate: () => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-700/40">
      <div className="flex items-center justify-between gap-2">
        <button
          onClick={() => setExpanded((p) => !p)}
          className="flex flex-1 items-center gap-2 text-left"
        >
          <ChevronIcon open={expanded} />
          <span className="text-xs font-medium text-gray-700 dark:text-gray-200">{prompt.name}</span>
        </button>
        <div className="flex items-center gap-1.5 shrink-0">
          {prompt.is_active && <Badge tone="green">Active</Badge>}
          {isAdmin && !prompt.is_active && (
            <Button size="sm" variant="secondary" onClick={onActivate}>
              Activate
            </Button>
          )}
          {isAdmin && (
            <Button size="sm" variant="danger" onClick={onDelete}>
              Del
            </Button>
          )}
        </div>
      </div>
      {expanded && (
        <pre className="mt-2 whitespace-pre-wrap text-xs text-gray-500 dark:text-gray-400 font-sans">
          {prompt.content}
        </pre>
      )}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const { current: service } = useService();
  const { user } = useAuth();
  const qc = useQueryClient();

  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [showPrompts, setShowPrompts] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevServiceIdRef = useRef<number | null>(null);

  const isAdmin = user?.is_superadmin || false;

  const { data: prompts = [] } = useQuery({
    queryKey: ["system-prompts", service?.id],
    queryFn: () => SystemPromptsApi.list(service!.id),
    enabled: !!service,
  });
  const activePrompt = prompts.find((p) => p.is_active);

  const { data: sessions = [], isSuccess: sessionsLoaded } = useQuery({
    queryKey: ["sessions", service?.id],
    queryFn: () => SessionsApi.list(service!.id),
    enabled: !!service,
  });

  const createSession = useMutation({
    mutationFn: () => SessionsApi.create(service!.id),
    onSuccess: (session) => {
      qc.invalidateQueries({ queryKey: ["sessions", service?.id] });
      setActiveSessionId(session.id);
      setTurns([]);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to create session"),
  });

  const deleteSession = useMutation({
    mutationFn: (sessionId: number) => SessionsApi.remove(service!.id, sessionId),
    onSuccess: (_, deletedId) => {
      qc.invalidateQueries({ queryKey: ["sessions", service?.id] });
      if (activeSessionId === deletedId) {
        const remaining = sessions.filter((s) => s.id !== deletedId);
        if (remaining.length > 0) {
          setActiveSessionId(remaining[0].id);
        } else {
          setActiveSessionId(null);
          setTurns([]);
        }
      }
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to delete session"),
  });

  // Reset when service changes
  useEffect(() => {
    if (!service) return;
    if (service.id === prevServiceIdRef.current) return;
    prevServiceIdRef.current = service.id;
    setActiveSessionId(null);
    setTurns([]);
  }, [service?.id]);

  // Auto-select first session once sessions load
  useEffect(() => {
    if (!sessionsLoaded || activeSessionId != null) return;
    if (sessions.length > 0) {
      setActiveSessionId(sessions[0].id);
    }
  }, [sessionsLoaded, sessions, activeSessionId]);

  // Load messages from DB when active session changes
  useEffect(() => {
    if (!service || !activeSessionId) {
      setTurns([]);
      return;
    }

    let cancelled = false;
    setLoadingMessages(true);
    setTurns([]);

    SessionsApi.messages(service.id, activeSessionId)
      .then((messages) => {
        if (cancelled) return;
        setTurns(
          messages.map((m) => ({
            id: crypto.randomUUID(),
            role: m.role as ChatRole,
            content: m.content,
            agentSteps: [],
            sources: [],
            isStreaming: false,
          })),
        );
      })
      .catch(() => {
        if (!cancelled) toast.error("Failed to load messages");
      })
      .finally(() => {
        if (!cancelled) setLoadingMessages(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeSessionId, service?.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function sendMessage() {
    if (!service || !activeSessionId || !input.trim() || streaming) return;
    const query = input.trim();
    setInput("");
    setStreaming(true);

    const userTurn: ChatTurn = {
      id: crypto.randomUUID(),
      role: "user",
      content: query,
      agentSteps: [],
      sources: [],
      isStreaming: false,
    };
    const assistantId = crypto.randomUUID();
    const assistantTurn: ChatTurn = {
      id: assistantId,
      role: "assistant",
      content: "",
      agentSteps: [],
      sources: [],
      isStreaming: true,
    };

    setTurns((prev) => [...prev, userTurn, assistantTurn]);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      let steps: AgentStep[] = [];
      let sources: SourceItem[] = [];
      let content = "";

      for await (const { event, data } of SessionsApi.chat(
        service.id,
        activeSessionId,
        query,
        undefined,
        ctrl.signal,
      )) {
        if (event === "agent_step") {
          const payload = JSON.parse(data) as { type: string; tool: string; input?: string; output?: SourceItem[] };
          const step: AgentStep = {
            type: payload.type as "tool_call" | "observation",
            tool: payload.tool,
            input: payload.input,
            output: payload.output,
          };
          steps = [...steps, step];
          if (payload.type === "observation" && payload.output) {
            sources = [...sources, ...payload.output];
          }
          setTurns((prev) =>
            prev.map((t) => (t.id === assistantId ? { ...t, agentSteps: steps } : t)),
          );
        } else if (event === "token") {
          const payload = JSON.parse(data) as { delta: string };
          content += payload.delta;
          setTurns((prev) =>
            prev.map((t) => (t.id === assistantId ? { ...t, content } : t)),
          );
        } else if (event === "done") {
          setTurns((prev) =>
            prev.map((t) =>
              t.id === assistantId ? { ...t, isStreaming: false, sources } : t,
            ),
          );
        } else if (event === "error") {
          const payload = JSON.parse(data) as { error: string };
          setTurns((prev) =>
            prev.map((t) =>
              t.id === assistantId ? { ...t, isStreaming: false, error: payload.error } : t,
            ),
          );
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setTurns((prev) =>
          prev.map((t) =>
            t.id === assistantId ? { ...t, isStreaming: false, error: String(e) } : t,
          ),
        );
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
      qc.invalidateQueries({ queryKey: ["sessions", service.id] });
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function stopStream() {
    abortRef.current?.abort();
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Sessions sidebar */}
      <Card className="w-52 shrink-0 overflow-hidden flex flex-col p-0">
        <SessionSidebar
          sessions={sessions}
          activeId={activeSessionId}
          onSelect={(id) => {
            if (id !== activeSessionId) {
              stopStream();
              setActiveSessionId(id);
            }
          }}
          onDelete={(id) => deleteSession.mutate(id)}
          onNew={() => createSession.mutate()}
          creating={createSession.isPending}
          disabled={!service}
        />
      </Card>

      {/* Chat area */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header */}
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {activePrompt ? (
              <Badge tone="green">{activePrompt.name}</Badge>
            ) : (
              <Badge tone="slate">Default prompt</Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setShowPrompts((p) => !p)}
              className="flex items-center gap-1.5"
            >
              <GearIcon />
              Prompts
            </Button>
          </div>
        </div>

        {/* Messages */}
        <Card className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {!service ? (
              <div className="flex h-full items-center justify-center text-sm text-gray-400">
                Select a service to start chatting.
              </div>
            ) : loadingMessages ? (
              <div className="flex h-full items-center justify-center">
                <span className="inline-flex gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-300 [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-300 [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-300" />
                </span>
              </div>
            ) : !activeSessionId ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-gray-400">
                <p>No session selected.</p>
                <Button size="sm" onClick={() => createSession.mutate()} disabled={createSession.isPending}>
                  Start new chat
                </Button>
              </div>
            ) : turns.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-gray-400">
                Ask anything about your documents.
              </div>
            ) : (
              turns.map((turn) => <MessageBubble key={turn.id} turn={turn} />)
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-100 p-3 dark:border-gray-700">
            <div className="flex gap-2">
              <Textarea
                rows={2}
                className="resize-none text-sm"
                placeholder={
                  !service
                    ? "Select a service first"
                    : !activeSessionId
                      ? "Create a session to start"
                      : "Ask a question… (Enter to send, Shift+Enter for newline)"
                }
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={!service || !activeSessionId || streaming}
              />
              {streaming ? (
                <Button variant="danger" onClick={stopStream} className="self-end">
                  Stop
                </Button>
              ) : (
                <Button
                  onClick={sendMessage}
                  disabled={!service || !activeSessionId || !input.trim()}
                  className="self-end flex items-center gap-1.5"
                >
                  <SendIcon />
                  Send
                </Button>
              )}
            </div>
          </div>
        </Card>
      </div>

      {/* System prompts panel */}
      {showPrompts && service && (
        <Card className="w-80 shrink-0 overflow-hidden flex flex-col">
          <SystemPromptsPanel
            serviceId={service.id}
            onClose={() => setShowPrompts(false)}
            isAdmin={isAdmin}
          />
        </Card>
      )}
    </div>
  );
}
