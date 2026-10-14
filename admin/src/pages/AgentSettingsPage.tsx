import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { AgentsApi, PipelineApi } from "@/api/endpoints";
import type {
  AgentAccent,
  AgentConfig,
  AgentRouteName,
  GraphTopology,
  LlmProvider,
  RetrievalMode,
} from "@/api/types";
import { ExecutionGraph } from "@/components/chat/ExecutionGraph";
import { Button, Card, Input, Label, Select, Textarea } from "@/components/ui";
import { ACCENT_THEMES, getAgentTheme } from "@/lib/agentTheme";
import { cn } from "@/lib/cn";
import { useService } from "@/services/ServiceProvider";

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
  const { current: agent, services: allAgents, refresh } = useService();
  const qc = useQueryClient();
  const agentId = agent?.id;

  const { data: saved, isLoading } = useQuery({
    queryKey: ["agent-config", agentId],
    queryFn: () => AgentsApi.getConfig(agentId!),
    enabled: agentId != null,
  });
  const { data: providers = [] } = useQuery({ queryKey: ["llm-providers"], queryFn: AgentsApi.providers });
  const { data: pipelines = [] } = useQuery({
    queryKey: ["pipelines", agentId],
    queryFn: () => PipelineApi.list(agentId!),
    enabled: agentId != null,
  });
  const activePipelines = pipelines.filter((p) => p.status === "active");

  // The working copy the form edits; `saved` stays the server's truth.
  const [draft, setDraft] = useState<AgentConfig | null>(null);
  useEffect(() => {
    if (saved) setDraft(saved);
  }, [saved]);

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(saved), [draft, saved]);
  const patch = (update: Partial<AgentConfig>) => setDraft((d) => (d ? { ...d, ...update } : d));

  // ── Live router preview ──
  const [previewMode, setPreviewMode] = useState<RetrievalMode | null>(null);
  const [topology, setTopology] = useState<GraphTopology | null>(null);
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
    return <Card className="p-8 text-sm text-gray-500">Only agent admins can change these settings.</Card>;
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
            <h1 className="text-xl font-bold text-[#2D3748] dark:text-gray-100">{agent.name}</h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">Agent settings · changes apply to the next message</p>
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

          {/* ── Delegation ── */}
          <Section
            title="Delegation"
            hint="Other agents this one may consult as tools when a question falls outside its own documents."
          >
            {allAgents.filter((a) => a.id !== agent.id).length === 0 ? (
              <p className="text-xs text-gray-500 dark:text-gray-400">No other agents to delegate to.</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {allAgents
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
                            {other.agent_config.description || `${other.document_count} documents`}
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
