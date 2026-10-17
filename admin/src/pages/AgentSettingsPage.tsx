import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { AgentsApi, DocumentSetsApi, McpApi, PipelineApi } from "@/api/endpoints";
import type {
  AgentAccent,
  AgentConfig,
  AgentRouteName,
  GraphPreview,
  LlmProvider,
  McpApproval,
  McpServer,
  McpToolRef,
  RetrievalMode,
} from "@/api/types";
import { ExecutionGraph } from "@/components/chat/ExecutionGraph";
import { Badge, Button, Card, Input, Label, Select, Textarea } from "@/components/ui";
import { ACCENT_THEMES, getAgentTheme } from "@/lib/agentTheme";
import { cn } from "@/lib/cn";
import { useWorkspace } from "@/workspace/WorkspaceProvider";

const ROUTE_ORDER: AgentRouteName[] = ["retrieval", "summary", "comparison", "direct"];

const ROUTE_HELP: Record<AgentRouteName, string> = {
  retrieval: "Looks up documents, then answers with citations.",
  summary: "Searches several angles and writes a structured summary.",
  comparison: "Plans one query per item, retrieves in parallel, compares.",
  direct: "Answers from the model alone, no document lookup.",
};

const ICON_PRESETS = ["🤖", "📚", "⚖️", "💰", "🏭", "🏥", "🧪", "🛠️", "📈", "🧭"];
const MODES: RetrievalMode[] = ["auto", "on", "off"];
const PREVIEW_DEBOUNCE_MS = 350;

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <Card className="p-5">
      <h2 className="text-sm font-bold text-[#2D3748] dark:text-gray-100">{title}</h2>
      {hint && <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{hint}</p>}
      <div className="mt-4 space-y-4">{children}</div>
    </Card>
  );
}

function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: T[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-xl border border-gray-200 p-0.5 dark:border-gray-600">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={cn(
            "rounded-lg px-3 py-1 text-xs capitalize transition-colors",
            value === opt
              ? "bg-teal-500 text-white shadow-sm"
              : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200",
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

/** Number input where blank means "inherit config.yaml". */
function OptionalNumber({
  id,
  value,
  onChange,
  min,
  max,
  placeholder,
}: {
  id: string;
  value: number | null;
  onChange: (v: number | null) => void;
  min: number;
  max: number;
  placeholder: string;
}) {
  return (
    <Input
      id={id}
      type="number"
      min={min}
      max={max}
      value={value ?? ""}
      placeholder={placeholder}
      onChange={(e) => {
        const raw = e.target.value;
        if (raw === "") return onChange(null);
        const n = Math.round(Number(raw));
        onChange(Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : null);
      }}
    />
  );
}

export default function AgentSettingsPage() {
  const { agent, agents: workspaceAgents, selectAgent, refresh } = useWorkspace();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const agentId = agent?.id;

  const { data: saved, isLoading } = useQuery({
    queryKey: ["agent-config", agentId],
    queryFn: () => AgentsApi.getConfig(agentId!),
    enabled: agentId != null,
  });
  const { data: providers = [] } = useQuery({ queryKey: ["llm-providers"], queryFn: AgentsApi.providers });
  const { data: pipelines = [] } = useQuery({
    queryKey: ["pipelines", agent?.workspace_id],
    queryFn: () => PipelineApi.list(agent!.workspace_id),
    enabled: agent != null,
  });
  const activePipelines = pipelines.filter((p) => p.status === "active");

  const { data: documentSets = [] } = useQuery({
    queryKey: ["document-sets", agent?.workspace_id],
    queryFn: () => DocumentSetsApi.list(agent!.workspace_id),
    enabled: agent != null,
  });
  const { data: mcpServers = [] } = useQuery({
    queryKey: ["mcp-servers", agent?.workspace_id],
    queryFn: () => McpApi.list(agent!.workspace_id),
    enabled: agent != null,
  });
  // Delegates can live in any workspace the user belongs to.
  const { data: reachableAgents = [] } = useQuery({ queryKey: ["agents-all"], queryFn: () => AgentsApi.listMine() });

  const [name, setName] = useState(agent?.name ?? "");
  useEffect(() => setName(agent?.name ?? ""), [agent?.id, agent?.name]);
  const rename = useMutation({
    mutationFn: () => AgentsApi.rename(agentId!, name.trim()),
    onSuccess: () => {
      toast.success("Agent renamed");
      void refresh();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to rename"),
  });
  const [confirmDelete, setConfirmDelete] = useState(false);
  const removeAgent = useMutation({
    mutationFn: () => AgentsApi.remove(agentId!),
    onSuccess: async () => {
      toast.success("Agent deleted");
      await refresh();
      navigate("/");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to delete"),
  });

  // The working copy the form edits; `saved` stays the server's truth.
  const [draft, setDraft] = useState<AgentConfig | null>(null);
  useEffect(() => {
    if (saved) setDraft(saved);
  }, [saved]);

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(saved), [draft, saved]);
  const patch = (update: Partial<AgentConfig>) => setDraft((d) => (d ? { ...d, ...update } : d));

  // ── Live router preview ──
  const [previewMode, setPreviewMode] = useState<RetrievalMode | null>(null);
  const [topology, setTopology] = useState<GraphPreview | null>(null);
  useEffect(() => {
    if (!draft || agentId == null) return;
    const handle = setTimeout(() => {
      AgentsApi.previewGraph(agentId, draft, previewMode ?? undefined)
        .then(setTopology)
        .catch(() => setTopology(null));
    }, PREVIEW_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [draft, previewMode, agentId]);

  const save = useMutation({
    mutationFn: (cfg: AgentConfig) => AgentsApi.updateConfig(agentId!, cfg),
    onSuccess: (cfg) => {
      qc.setQueryData(["agent-config", agentId], cfg);
      void refresh(); // landing cards and the switcher read from here
      toast.success("Agent settings saved");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to save"),
  });

  if (!agent) {
    return <Card className="p-8 text-sm text-gray-500">Select an agent first.</Card>;
  }
  if (agent.role !== "admin") {
    return <Card className="p-8 text-sm text-gray-500">Only workspace admins can change agent settings.</Card>;
  }
  if (isLoading || !draft) {
    return <div className="h-96 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800" />;
  }

  const theme = getAgentTheme({ ...agent, agent_config: draft });
  const providerInfo = providers.find((p) => p.provider === draft.llm.provider);
  const modelSuggestions = providerInfo?.models ?? [];
  const enabledRoutes = ROUTE_ORDER.filter((r) => draft.routes[r].enabled);

  const setRoute = (name: AgentRouteName, update: Partial<AgentConfig["routes"][AgentRouteName]>) =>
    patch({ routes: { ...draft.routes, [name]: { ...draft.routes[name], ...update } } });

  const setQuestion = (index: number, value: string) => {
    const next = [...draft.starter_questions];
    next[index] = value;
    patch({ starter_questions: next });
  };

  return (
    <div className="mx-auto max-w-6xl pb-20">
      {/* Header */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            className="flex h-11 w-11 items-center justify-center rounded-xl text-2xl text-white shadow-sm"
            style={{ background: `linear-gradient(135deg, ${theme.gradientFrom}, ${theme.gradientTo})` }}
          >
            {theme.icon}
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-[#2D3748] dark:text-gray-100">{agent.name}</h1>
              {workspaceAgents.length > 1 && (
                <Select
                  className="w-auto py-1 text-xs"
                  value={agent.id}
                  aria-label="Switch agent"
                  onChange={(e) => {
                    const next = workspaceAgents.find((a) => a.id === Number(e.target.value));
                    if (next) selectAgent(next);
                  }}
                >
                  {workspaceAgents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </Select>
              )}
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {agent.workspace_name} · changes apply to the next message
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {dirty && <span className="text-xs text-amber-600 dark:text-amber-400">Unsaved changes</span>}
          <Button variant="secondary" size="sm" disabled={!dirty} onClick={() => setDraft(saved!)}>
            Reset
          </Button>
          <Button size="sm" disabled={!dirty || save.isPending} onClick={() => save.mutate(draft)}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          {/* ── Profile ── */}
          <Section title="Profile" hint="How this agent appears on the landing page.">
            <div>
              <Label htmlFor="agent-name">Name</Label>
              <div className="flex gap-2">
                <Input id="agent-name" value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!name.trim() || name.trim() === agent.name || rename.isPending}
                  onClick={() => rename.mutate()}
                >
                  Rename
                </Button>
              </div>
            </div>
            <div>
              <Label>Icon & color</Label>
              <div className="flex flex-wrap items-center gap-1.5">
                {ICON_PRESETS.map((icon) => (
                  <button
                    key={icon}
                    type="button"
                    onClick={() => patch({ icon })}
                    className={cn(
                      "flex h-9 w-9 items-center justify-center rounded-lg border text-lg transition-colors",
                      theme.icon === icon
                        ? "border-teal-400 bg-teal-50 dark:bg-teal-900/30"
                        : "border-gray-200 hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700",
                    )}
                  >
                    {icon}
                  </button>
                ))}
                <span className="mx-2 h-6 w-px bg-gray-200 dark:bg-gray-600" />
                {(Object.keys(ACCENT_THEMES) as AgentAccent[]).map((accent) => (
                  <button
                    key={accent}
                    type="button"
                    aria-label={accent}
                    onClick={() => patch({ accent })}
                    className={cn(
                      "h-7 w-7 rounded-full transition-transform",
                      draft.accent === accent && "ring-2 ring-offset-2 ring-gray-400 dark:ring-offset-gray-800",
                    )}
                    style={{
                      background: `linear-gradient(135deg, ${ACCENT_THEMES[accent].gradientFrom}, ${ACCENT_THEMES[accent].gradientTo})`,
                    }}
                  />
                ))}
              </div>
            </div>
            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                rows={2}
                maxLength={500}
                value={draft.description}
                placeholder="What does this agent know about?"
                onChange={(e) => patch({ description: e.target.value })}
              />
            </div>
            <div>
              <Label>Starter questions</Label>
              <p className="mb-2 text-[11px] text-gray-500 dark:text-gray-400">
                Shown as one-click prompts on the landing card and in an empty chat. Up to 6.
              </p>
              <div className="space-y-1.5">
                {draft.starter_questions.map((q, i) => (
                  <div key={i} className="flex gap-1.5">
                    <Input value={q} onChange={(e) => setQuestion(i, e.target.value)} />
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        patch({ starter_questions: draft.starter_questions.filter((_, j) => j !== i) })
                      }
                    >
                      ✕
                    </Button>
                  </div>
                ))}
                {draft.starter_questions.length < 6 && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => patch({ starter_questions: [...draft.starter_questions, ""] })}
                  >
                    + Add question
                  </Button>
                )}
              </div>
            </div>
          </Section>

          {/* ── Model ── */}
          <Section title="Model" hint="Leave a field on its default to inherit config.yaml. API keys stay in .env.">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="provider">Provider</Label>
                <Select
                  id="provider"
                  value={draft.llm.provider ?? ""}
                  onChange={(e) =>
                    patch({
                      // A model name rarely carries across providers, so reset it.
                      llm: { ...draft.llm, provider: (e.target.value || null) as LlmProvider | null, model: null },
                    })
                  }
                >
                  <option value="">Default (config.yaml)</option>
                  {providers.map((p) => (
                    <option key={p.provider} value={p.provider} disabled={!p.available}>
                      {p.provider}
                      {p.available ? "" : ` — ${p.reason}`}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="model">Model</Label>
                <Input
                  id="model"
                  list="model-suggestions"
                  value={draft.llm.model ?? ""}
                  placeholder={modelSuggestions[0] ?? "default model"}
                  onChange={(e) => patch({ llm: { ...draft.llm, model: e.target.value || null } })}
                />
                <datalist id="model-suggestions">
                  {modelSuggestions.map((m) => (
                    <option key={m} value={m} />
                  ))}
                </datalist>
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between">
                <Label htmlFor="temperature">Temperature</Label>
                <label className="flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400">
                  <input
                    type="checkbox"
                    checked={draft.llm.temperature == null}
                    onChange={(e) =>
                      patch({ llm: { ...draft.llm, temperature: e.target.checked ? null : 0.2 } })
                    }
                  />
                  inherit
                </label>
              </div>
              <div className="flex items-center gap-3">
                <input
                  id="temperature"
                  type="range"
                  min={0}
                  max={2}
                  step={0.1}
                  disabled={draft.llm.temperature == null}
                  value={draft.llm.temperature ?? 0}
                  onChange={(e) => patch({ llm: { ...draft.llm, temperature: Number(e.target.value) } })}
                  className="flex-1 accent-teal-500 disabled:opacity-40"
                />
                <span className="w-10 text-right font-mono text-xs text-gray-600 dark:text-gray-300">
                  {draft.llm.temperature == null ? "—" : draft.llm.temperature.toFixed(1)}
                </span>
              </div>
            </div>
          </Section>

          {/* ── Document sets ── */}
          <Section
            title="Document sets"
            hint="The documents this agent searches. With no set selected it searches nothing and answers from the model alone."
          >
            {documentSets.length === 0 ? (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                This workspace has no document sets yet, so the agent has no documents to search.{" "}
                <Link to="/document-sets" className="text-teal-600 hover:underline">
                  Create one
                </Link>
              </p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {documentSets.map((ds) => {
                  const on = draft.document_set_ids.includes(ds.id);
                  return (
                    <label
                      key={ds.id}
                      className={cn(
                        "flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors",
                        on
                          ? "border-teal-300 bg-teal-50/60 dark:border-teal-800 dark:bg-teal-900/10"
                          : "border-gray-200 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/40",
                      )}
                    >
                      <input
                        type="checkbox"
                        className="mt-0.5 accent-teal-500"
                        checked={on}
                        onChange={() =>
                          patch({
                            document_set_ids: on
                              ? draft.document_set_ids.filter((id) => id !== ds.id)
                              : [...draft.document_set_ids, ds.id],
                          })
                        }
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-[#2D3748] dark:text-gray-100">
                          {ds.name}
                        </span>
                        <span className="block truncate text-[11px] text-gray-500 dark:text-gray-400">
                          {ds.document_ids.length} documents{ds.description ? ` · ${ds.description}` : ""}
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
            <p className="text-[11px] text-gray-500 dark:text-gray-400">
              {draft.document_set_ids.length === 0 ? (
                <span className="font-semibold text-amber-600 dark:text-amber-400">
                  No set selected — this agent searches no documents.
                </span>
              ) : (
                `Searching ${topology?.document_count ?? "…"} document(s) across ${draft.document_set_ids.length} set(s).`
              )}
            </p>
          </Section>

          {/* ── Retrieval ── */}
          <Section title="Retrieval" hint="Where and how much this agent searches before answering.">
            <div>
              <Label htmlFor="pipeline">Search pipeline</Label>
              <Select
                id="pipeline"
                value={draft.pipeline_id ?? ""}
                onChange={(e) => patch({ pipeline_id: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">Built-in (embed → vector search → rerank)</option>
                {activePipelines.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
              <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">
                Only active pipelines from the Pipeline Builder can serve chat.
                {pipelines.length > activePipelines.length &&
                  ` ${pipelines.length - activePipelines.length} draft/archived hidden.`}
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <Label htmlFor="top_k">Results per search</Label>
                <OptionalNumber
                  id="top_k"
                  value={draft.top_k}
                  min={1}
                  max={50}
                  placeholder="default"
                  onChange={(top_k) => patch({ top_k })}
                />
              </div>
              <div>
                <Label htmlFor="max_iterations">Max tool rounds</Label>
                <OptionalNumber
                  id="max_iterations"
                  value={draft.max_iterations}
                  min={1}
                  max={10}
                  placeholder="default"
                  onChange={(max_iterations) => patch({ max_iterations })}
                />
              </div>
              <div>
                <Label>Default mode</Label>
                <Segmented
                  options={MODES}
                  value={draft.default_retrieval_mode}
                  onChange={(default_retrieval_mode) => patch({ default_retrieval_mode })}
                />
              </div>
            </div>
          </Section>

          {/* ── MCP tools ── */}
          <Section
            title="MCP tools"
            hint="Tools from this workspace's MCP servers. Lookups can run on their own; anything that changes data should wait for the user's approval in the chat."
          >
            <McpToolPicker
              servers={mcpServers}
              value={draft.mcp_tools ?? []}
              onChange={(mcp_tools) => patch({ mcp_tools })}
            />
          </Section>

          {/* ── Delegation ── */}
          <Section
            title="Delegation"
            hint="Other agents this one may consult as tools when a question falls outside its own documents."
          >
            {reachableAgents.filter((a) => a.id !== agent.id).length === 0 ? (
              <p className="text-xs text-gray-500 dark:text-gray-400">No other agents to delegate to.</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {reachableAgents
                  .filter((a) => a.id !== agent.id)
                  .map((other) => {
                    const on = draft.delegates.includes(other.id);
                    const t = getAgentTheme(other);
                    return (
                      <button
                        key={other.id}
                        type="button"
                        onClick={() =>
                          patch({
                            delegates: on
                              ? draft.delegates.filter((id) => id !== other.id)
                              : [...draft.delegates, other.id],
                          })
                        }
                        className={cn(
                          "flex items-center gap-3 rounded-xl border p-3 text-left transition-colors",
                          on
                            ? "border-rose-300 bg-rose-50/60 dark:border-rose-800 dark:bg-rose-900/10"
                            : "border-gray-200 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/40",
                        )}
                      >
                        <span
                          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-lg text-white"
                          style={{ background: `linear-gradient(135deg, ${t.gradientFrom}, ${t.gradientTo})` }}
                        >
                          {t.icon}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-[#2D3748] dark:text-gray-100">
                            {other.name}
                          </span>
                          <span className="block truncate text-[11px] text-gray-500 dark:text-gray-400">
                            {other.workspace_name} · {other.agent_config.description || `${other.document_count} documents`}
                          </span>
                        </span>
                        <input type="checkbox" readOnly checked={on} className="accent-rose-500" />
                      </button>
                    );
                  })}
              </div>
            )}
            <p className="text-[11px] text-gray-500 dark:text-gray-400">
              Delegates run their own graph and return a plain-text answer. One level deep — a delegate never
              delegates further — and users only reach delegates they could chat with directly.
            </p>
          </Section>

          {/* ── Router ── */}
          <Section
            title="Router"
            hint="Which specialists the supervisor can hand a question to, and how it tells them apart."
          >
            {ROUTE_ORDER.map((name) => {
              const route = draft.routes[name];
              return (
                <div
                  key={name}
                  className={cn(
                    "rounded-xl border p-3 transition-colors",
                    route.enabled
                      ? "border-teal-200 bg-teal-50/40 dark:border-teal-800 dark:bg-teal-900/10"
                      : "border-gray-200 opacity-70 dark:border-gray-700",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold capitalize text-[#2D3748] dark:text-gray-100">{name}</p>
                      <p className="text-[11px] text-gray-500 dark:text-gray-400">{ROUTE_HELP[name]}</p>
                    </div>
                    <label className="flex cursor-pointer items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
                      <input
                        type="checkbox"
                        className="accent-teal-500"
                        checked={route.enabled}
                        onChange={(e) => setRoute(name, { enabled: e.target.checked })}
                      />
                      enabled
                    </label>
                  </div>
                  {route.enabled && (
                    <Input
                      className="mt-2"
                      value={route.description}
                      maxLength={300}
                      placeholder="When should the supervisor pick this route?"
                      onChange={(e) => setRoute(name, { description: e.target.value })}
                    />
                  )}
                </div>
              );
            })}
            {enabledRoutes.length === 1 && (
              <p className="text-[11px] text-gray-500 dark:text-gray-400">
                With one route there is nothing to decide, so the supervisor is skipped — one fewer LLM call per
                message.
              </p>
            )}
            {enabledRoutes.length === 0 && (
              <p className="text-[11px] text-amber-600 dark:text-amber-400">
                No route enabled — the agent falls back to retrieval.
              </p>
            )}
          </Section>
          {/* ── Danger zone ── */}
          <Section title="Delete agent" hint="Removes this agent with its prompts, chats, evaluations and feedback. The workspace's documents and document sets stay.">
            {confirmDelete ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-rose-600">Delete {agent.name} permanently?</span>
                <Button size="sm" variant="secondary" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="bg-rose-500 hover:bg-rose-600"
                  disabled={removeAgent.isPending}
                  onClick={() => removeAgent.mutate()}
                >
                  {removeAgent.isPending ? "Deleting…" : "Delete agent"}
                </Button>
              </div>
            ) : (
              <Button size="sm" variant="secondary" onClick={() => setConfirmDelete(true)}>
                Delete this agent…
              </Button>
            )}
          </Section>
        </div>

        {/* ── Live preview ── */}
        <div className="lg:sticky lg:top-4 lg:self-start">
          <Card className="overflow-hidden p-0">
            <div className="flex items-center justify-between border-b px-4 py-3 dark:border-gray-700">
              <div>
                <p className="text-xs font-semibold text-gray-700 dark:text-gray-200">Router preview</p>
                <p className="text-[10px] text-gray-400">The graph chat will run, built from this draft.</p>
              </div>
            </div>
            <div className="flex items-center gap-2 border-b px-4 py-2 text-[11px] dark:border-gray-700">
              <span className="text-gray-400">Chat mode</span>
              <Segmented
                options={MODES}
                value={previewMode ?? draft.default_retrieval_mode}
                onChange={setPreviewMode}
              />
            </div>
            <div className="h-80">
              <ExecutionGraph
                topology={topology}
                nodeStatus={{}}
                streaming={false}
                preview
                emptyMessage="Building preview…"
              />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ── MCP tool picker ──────────────────────────────────────────────────────────

function McpToolPicker({
  servers,
  value,
  onChange,
}: {
  servers: McpServer[];
  value: McpToolRef[];
  onChange: (refs: McpToolRef[]) => void;
}) {
  if (servers.length === 0) {
    return (
      <p className="text-xs text-gray-500 dark:text-gray-400">
        No MCP servers in this workspace yet.{" "}
        <Link to="/mcp" className="text-teal-600 hover:underline">
          Add one
        </Link>
      </p>
    );
  }
  const find = (serverId: number, tool: string) => value.find((r) => r.server_id === serverId && r.tool === tool);
  const set = (serverId: number, tool: string, ref: McpToolRef | null) =>
    onChange([...value.filter((r) => !(r.server_id === serverId && r.tool === tool)), ...(ref ? [ref] : [])]);

  return (
    <div className="space-y-3">
      {servers.map((server) => {
        const chosen = value.filter((r) => r.server_id === server.id).length;
        const allOn = server.tools.length > 0 && chosen === server.tools.length;
        return (
          <div key={server.id} className="rounded-xl border border-gray-200 dark:border-gray-700">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 px-3 py-2 dark:border-gray-700">
              <div>
                <span className="text-sm font-semibold text-[#2D3748] dark:text-gray-100">{server.name}</span>
                <span className="ml-2 text-[11px] text-gray-400">
                  {chosen}/{server.tools.length} tools
                  {!server.enabled && " · server disabled"}
                  {server.last_error && " · connection failed"}
                </span>
              </div>
              {server.tools.length > 0 && (
                <button
                  type="button"
                  className="text-[11px] font-semibold text-teal-600 hover:underline"
                  onClick={() =>
                    onChange([
                      ...value.filter((r) => r.server_id !== server.id),
                      ...(allOn
                        ? []
                        : server.tools.map((t) => ({
                            server_id: server.id,
                            tool: t.name,
                            // Keep a choice already made; default writes to approval.
                            approval: find(server.id, t.name)?.approval ?? (t.read_only ? "auto" : "required"),
                          }) as McpToolRef)),
                    ])
                  }
                >
                  {allOn ? "Clear all" : "Select all"}
                </button>
              )}
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {server.tools.map((t) => {
                const ref = find(server.id, t.name);
                return (
                  <div key={t.name} className="flex flex-wrap items-center gap-3 px-3 py-2">
                    <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-2">
                      <input
                        type="checkbox"
                        className="mt-0.5 accent-teal-500"
                        checked={ref != null}
                        onChange={() =>
                          set(
                            server.id,
                            t.name,
                            ref ? null : { server_id: server.id, tool: t.name, approval: t.read_only ? "auto" : "required" },
                          )
                        }
                      />
                      <span className="min-w-0">
                        <span className="block text-xs font-semibold text-gray-700 dark:text-gray-200">
                          {t.title || t.name}{" "}
                          <span className="font-mono font-normal text-gray-400">{t.name}</span>
                        </span>
                        <span className="block truncate text-[11px] text-gray-400">{t.description.split("\n")[0]}</span>
                      </span>
                    </label>
                    {t.read_only ? (
                      <Badge tone="green">read-only</Badge>
                    ) : (
                      <Badge tone={t.destructive ? "red" : "amber"}>{t.destructive ? "destructive" : "writes"}</Badge>
                    )}
                    <div
                      className={cn(
                        "flex overflow-hidden rounded-lg border text-[11px] dark:border-gray-600",
                        !ref && "pointer-events-none opacity-40",
                      )}
                      role="radiogroup"
                      aria-label={`Approval for ${t.name}`}
                    >
                      {(["auto", "required"] as McpApproval[]).map((mode) => (
                        <button
                          key={mode}
                          type="button"
                          role="radio"
                          aria-checked={ref?.approval === mode}
                          onClick={() => ref && set(server.id, t.name, { ...ref, approval: mode })}
                          className={cn(
                            "px-2 py-1 font-semibold",
                            ref?.approval === mode
                              ? mode === "required"
                                ? "bg-violet-600 text-white"
                                : "bg-teal-500 text-white"
                              : "text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-700",
                          )}
                        >
                          {mode === "auto" ? "Run" : "Ask first"}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
      <p className="text-[11px] text-gray-500 dark:text-gray-400">
        “Ask first” tools pause the chat until the user approves, rejects or edits the call. They aren't offered where a
        run can't pause — the one-off chat API, evaluations, and when another agent delegates to this one.
      </p>
    </div>
  );
}
