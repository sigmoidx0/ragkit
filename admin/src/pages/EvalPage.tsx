import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { AgentsApi, DocumentsApi, EvalsApi, FeedbackApi, PipelineApi, SystemPromptsApi } from "@/api/endpoints";
import type {
  AgentConfig,
  EvalCase,
  EvalCaseResult,
  EvalRun,
  EvalSummary,
  LlmProvider,
  RetrievalMode,
  UnansweredItem,
} from "@/api/types";
import { Badge, Button, Card, Input, Label, Select } from "@/components/ui";
import { cn } from "@/lib/cn";
import { useWorkspace } from "@/workspace/WorkspaceProvider";

const RUN_COLORS = ["#14b8a6", "#8b5cf6"]; // A, B

// ── Formatting ────────────────────────────────────────────────────────────────

const fmtPct = (v: number | null) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const fmtNum = (v: number | null, digits = 2) => (v == null ? "—" : v.toFixed(digits));
const fmtMs = (v: number | null) => (v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${Math.round(v)}ms`);

function configLabel(cfg: AgentConfig): string {
  const model = cfg.llm.model ?? (cfg.llm.provider ? `${cfg.llm.provider} default` : "default model");
  const parts = [model, `top_k ${cfg.top_k ?? "default"}`];
  if (cfg.pipeline_id != null) parts.push(`pipeline #${cfg.pipeline_id}`);
  return parts.join(" · ");
}

// ── Metric cards ─────────────────────────────────────────────────────────────

interface MetricDef {
  label: string;
  hint: string;
  value: (s: EvalSummary) => number | null;
  format: (v: number | null) => string;
  /** Which direction is better, for colouring the A→B delta. */
  better: "higher" | "lower";
}

const METRICS: MetricDef[] = [
  { label: "Hit rate", hint: "expected document retrieved", value: (s) => s.hit_rate, format: fmtPct, better: "higher" },
  { label: "MRR", hint: "1 / rank of expected document", value: (s) => s.mrr, format: (v) => fmtNum(v), better: "higher" },
  {
    label: "Answer coverage",
    hint: "expected facts stated",
    value: (s) => s.keyword_recall,
    format: fmtPct,
    better: "higher",
  },
  {
    label: "Groundedness",
    hint: "LLM-judged support, 1–5",
    value: (s) => s.avg_groundedness,
    format: (v) => fmtNum(v, 1),
    better: "higher",
  },
  { label: "Avg latency", hint: "per question", value: (s) => s.avg_latency_ms, format: fmtMs, better: "lower" },
  { label: "p95 latency", hint: "slowest questions", value: (s) => s.p95_latency_ms, format: fmtMs, better: "lower" },
  {
    label: "Tool calls",
    hint: "avg searches + delegations",
    value: (s) => s.avg_tool_calls,
    format: (v) => fmtNum(v, 1),
    better: "lower",
  },
  {
    label: "Tokens",
    hint: "total in + out",
    value: (s) => s.total_tokens,
    format: (v) => (v == null ? "—" : v.toLocaleString()),
    better: "lower",
  },
];

function Delta({ a, b, metric }: { a: number | null; b: number | null; metric: MetricDef }) {
  if (a == null || b == null || a === b) return null;
  const improved = metric.better === "higher" ? b > a : b < a;
  const rel = a !== 0 ? Math.abs((b - a) / a) : null;
  return (
    <span className={cn("text-[11px] font-semibold", improved ? "text-teal-600 dark:text-teal-400" : "text-rose-500")}>
      {improved ? "▲" : "▼"} {rel != null ? `${Math.round(rel * 100)}%` : ""}
    </span>
  );
}

function MetricCards({ runs }: { runs: EvalRun[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8">
      {METRICS.map((m) => {
        const values = runs.map((r) => (r.summary ? m.value(r.summary) : null));
        return (
          <Card key={m.label} className="p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">{m.label}</p>
            <div className="mt-1 space-y-0.5">
              {values.map((v, i) => (
                <p key={i} className="flex items-baseline gap-1.5">
                  {runs.length > 1 && (
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: RUN_COLORS[i] }} />
                  )}
                  <span className="font-mono text-lg font-bold text-gray-800 dark:text-gray-100">{m.format(v)}</span>
                  {i === 1 && <Delta a={values[0]} b={v} metric={m} />}
                </p>
              ))}
            </div>
            <p className="mt-1 text-[10px] text-gray-400">{m.hint}</p>
          </Card>
        );
      })}
    </div>
  );
}

// ── Per-question table ───────────────────────────────────────────────────────

function HitCell({ r }: { r?: EvalCaseResult }) {
  if (!r) return <span className="text-gray-300">…</span>;
  if (r.error) return <Badge tone="red">error</Badge>;
  if (r.hit == null) return <span className="text-gray-300">—</span>;
  return r.hit ? <Badge tone="green">#{r.rank}</Badge> : <Badge tone="red">miss</Badge>;
}

function CoverageCell({ r }: { r?: EvalCaseResult }) {
  if (!r || r.keyword_recall == null) return <span className="text-gray-300">—</span>;
  const tone = r.keyword_recall >= 1 ? "green" : r.keyword_recall > 0 ? "amber" : "red";
  return <Badge tone={tone}>{Math.round(r.keyword_recall * 100)}%</Badge>;
}

function GroundCell({ r }: { r?: EvalCaseResult }) {
  if (!r || r.groundedness == null) return <span className="text-gray-300">—</span>;
  const tone = r.groundedness >= 4 ? "green" : r.groundedness === 3 ? "amber" : "red";
  return <Badge tone={tone}>{r.groundedness}/5</Badge>;
}

function CaseTable({ runs, docTitle }: { runs: EvalRun[]; docTitle: (id: number | null) => string }) {
  const [open, setOpen] = useState<number | null>(null);
  // Runs compared side by side share questions positionally when copied from
  // one another; fall back to the first run's cases.
  const cases = runs[0].cases;

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full text-left text-xs">
        <thead className="border-b text-[10px] uppercase tracking-wide text-gray-400 dark:border-gray-700">
          <tr>
            <th className="px-4 py-2.5">Question</th>
            <th className="px-2 py-2.5">Expected</th>
            {runs.map((run, i) => (
              <th key={run.id} className="px-2 py-2.5" colSpan={4}>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: RUN_COLORS[i] }} />
                  {run.name}
                </span>
              </th>
            ))}
          </tr>
          <tr className="text-[9px]">
            <th />
            <th />
            {runs.map((run) => (
              <Fragment key={run.id}>
                <th className="px-2 pb-2">hit</th>
                <th className="px-2 pb-2">facts</th>
                <th className="px-2 pb-2">ground</th>
                <th className="px-2 pb-2">time</th>
              </Fragment>
            ))}
          </tr>
        </thead>
        <tbody>
          {cases.map((c, i) => {
            const results = runs.map((run) => run.results[i]);
            return (
              <Fragment key={i}>
                <tr
                  onClick={() => setOpen(open === i ? null : i)}
                  className="cursor-pointer border-b transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/40"
                >
                  <td className="max-w-xs px-4 py-2.5 text-gray-700 dark:text-gray-200">
                    <span className="line-clamp-2">{c.question}</span>
                  </td>
                  <td className="max-w-[140px] truncate px-2 py-2.5 text-gray-500">{docTitle(c.expected_document_id)}</td>
                  {results.map((r, j) => (
                    <Fragment key={j}>
                      <td className="px-2 py-2.5"><HitCell r={r} /></td>
                      <td className="px-2 py-2.5"><CoverageCell r={r} /></td>
                      <td className="px-2 py-2.5"><GroundCell r={r} /></td>
                      <td className="px-2 py-2.5 font-mono text-gray-500">{r ? fmtMs(r.latency_ms) : "…"}</td>
                    </Fragment>
                  ))}
                </tr>
                {open === i && (
                  <tr className="border-b bg-gray-50/60 dark:border-gray-700 dark:bg-gray-900/20">
                    <td colSpan={2 + runs.length * 4} className="px-4 py-3">
                      <div className={cn("grid gap-3", runs.length > 1 && "lg:grid-cols-2")}>
                        {results.map((r, j) => (
                          <div key={j} className="rounded-xl border bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
                            <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold text-gray-500">
                              <span className="h-2 w-2 rounded-full" style={{ background: RUN_COLORS[j] }} />
                              {runs[j].name}
                              {r && (
                                <span className="font-normal text-gray-400">
                                  · {r.route ?? "?"} · {r.tool_calls} tool calls · {r.input_tokens}→{r.output_tokens} tok
                                </span>
                              )}
                            </p>
                            {!r ? (
                              <p className="text-xs text-gray-400">Not run yet.</p>
                            ) : r.error ? (
                              <p className="text-xs text-rose-500">{r.error}</p>
                            ) : (
                              <>
                                <p className="whitespace-pre-wrap text-xs leading-relaxed text-gray-700 dark:text-gray-200">
                                  {r.answer}
                                </p>
                                {r.missing_keywords.length > 0 && (
                                  <p className="mt-2 text-[11px] text-amber-600 dark:text-amber-400">
                                    Missing facts: {r.missing_keywords.join(", ")}
                                  </p>
                                )}
                                {r.judge_reason && (
                                  <p className="mt-2 rounded-lg bg-gray-50 px-2 py-1.5 text-[11px] text-gray-500 dark:bg-gray-700/40 dark:text-gray-400">
                                    Judge: {r.judge_reason}
                                  </p>
                                )}
                                {r.sources.length > 0 && (
                                  <p className="mt-2 text-[10px] text-gray-400">
                                    Sources:{" "}
                                    {[...new Set(r.sources.map((s) => s.title ?? `#${s.document_id}`))].join(", ")}
                                  </p>
                                )}
                              </>
                            )}
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

// ── New evaluation ───────────────────────────────────────────────────────────

/**
 * Comma-separated keywords. Keeps the raw text while typing — re-joining the
 * parsed list on every keystroke would swallow the comma just typed.
 */
const parseKeywords = (raw: string) => raw.split(",").map((k) => k.trim()).filter(Boolean);

function KeywordsInput({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const [raw, setRaw] = useState(value.join(", "));
  // Rows are keyed by position, so deleting one hands this input its
  // neighbour's keywords — resync when the value stops matching what we hold.
  useEffect(() => {
    if (parseKeywords(raw).join("\u0000") !== value.join("\u0000")) setRaw(value.join(", "));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return (
    <Input
      className="w-40 shrink-0"
      value={raw}
      placeholder="facts, comma-separated"
      title="Words a correct answer must contain"
      onChange={(e) => {
        setRaw(e.target.value);
        onChange(parseKeywords(e.target.value));
      }}
    />
  );
}

interface VariantOverrides {
  provider: LlmProvider | "";
  model: string;
  top_k: string;
  max_iterations: string;
  pipeline_id: string;
  default_retrieval_mode: RetrievalMode | "";
}

const NO_OVERRIDES: VariantOverrides = {
  provider: "",
  model: "",
  top_k: "",
  max_iterations: "",
  pipeline_id: "",
  default_retrieval_mode: "",
};

function applyOverrides(base: AgentConfig, o: VariantOverrides): AgentConfig {
  return {
    ...base,
    llm: {
      ...base.llm,
      provider: o.provider || base.llm.provider,
      model: o.model || (o.provider ? null : base.llm.model),
    },
    top_k: o.top_k ? Number(o.top_k) : base.top_k,
    max_iterations: o.max_iterations ? Number(o.max_iterations) : base.max_iterations,
    pipeline_id: o.pipeline_id === "builtin" ? null : o.pipeline_id ? Number(o.pipeline_id) : base.pipeline_id,
    default_retrieval_mode: o.default_retrieval_mode || base.default_retrieval_mode,
  };
}

function NewEvalPanel({
  agentId,
  workspaceId,
  runs,
  documents,
  initialCases,
  onClose,
  onCreated,
}: {
  agentId: number;
  workspaceId: number;
  runs: EvalRun[];
  documents: { id: number; title: string }[];
  /** Questions to start from — e.g. answers users rated 👎. */
  initialCases?: EvalCase[];
  onClose: () => void;
  onCreated: (run: EvalRun) => void;
}) {
  const { data: saved } = useQuery({ queryKey: ["agent-config", agentId], queryFn: () => AgentsApi.getConfig(agentId) });
  const { data: providers = [] } = useQuery({ queryKey: ["llm-providers"], queryFn: AgentsApi.providers });
  const { data: pipelines = [] } = useQuery({
    queryKey: ["pipelines", workspaceId],
    queryFn: () => PipelineApi.list(workspaceId),
  });

  const [name, setName] = useState(`Run ${runs.length + 1}`);
  const { data: prompts = [] } = useQuery({
    queryKey: ["system-prompts", agentId],
    queryFn: () => SystemPromptsApi.list(agentId),
  });
  const [cases, setCases] = useState<EvalCase[]>(
    initialCases ?? runs[0]?.cases ?? [{ question: "", expected_document_id: null }],
  );
  const [promptId, setPromptId] = useState<number | null>(null);
  const [variant, setVariant] = useState(false);
  const [o, setO] = useState<VariantOverrides>(NO_OVERRIDES);

  const create = useMutation({
    mutationFn: () => {
      const clean = cases.filter((c) => c.question.trim());
      return EvalsApi.create(agentId, {
        name,
        cases: clean,
        config: variant && saved ? applyOverrides(saved, o) : null,
        system_prompt_id: promptId,
      });
    },
    onSuccess: (run) => {
      toast.success("Evaluation started");
      onCreated(run);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to start"),
  });

  const setCase = (i: number, update: Partial<EvalCase>) =>
    setCases((cs) => cs.map((c, j) => (j === i ? { ...c, ...update } : c)));
  const providerModels = providers.find((p) => p.provider === o.provider)?.models ?? [];
  const ready = name.trim() && cases.some((c) => c.question.trim());

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-bold text-[#2D3748] dark:text-gray-100">New evaluation</h2>
        <button onClick={onClose} className="text-xs text-gray-400 hover:text-gray-600">
          Cancel
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_minmax(0,1.6fr)]">
        <div className="space-y-4">
          <div>
            <Label htmlFor="eval-name">Name</Label>
            <Input id="eval-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          {runs.length > 0 && (
            <div>
              <Label htmlFor="copy-from">Questions from</Label>
              <Select id="copy-from" onChange={(e) => {
                const run = runs.find((r) => r.id === Number(e.target.value));
                if (run) setCases(run.cases);
              }} defaultValue="">
                <option value="" disabled>
                  Copy from a previous run…
                </option>
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.cases.length} questions)
                  </option>
                ))}
              </Select>
              <p className="mt-1 text-[11px] text-gray-400">Same questions on both runs makes them comparable.</p>
            </div>
          )}

          <div>
            <Label htmlFor="eval-prompt">System prompt</Label>
            <Select
              id="eval-prompt"
              value={promptId ?? ""}
              onChange={(e) => setPromptId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Active prompt{prompts.find((p) => p.is_active) ? ` (${prompts.find((p) => p.is_active)!.name})` : ""}</option>
              {prompts.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.is_active ? " — active" : ""}
                </option>
              ))}
            </Select>
            <p className="mt-1 text-[11px] text-gray-400">
              Try a draft prompt against the same questions before activating it.
            </p>
          </div>

          <div>
            <Label>Configuration</Label>
            <div className="flex gap-2 text-xs">
              {[
                { v: false, label: "Saved settings" },
                { v: true, label: "Variant" },
              ].map(({ v, label }) => (
                <button
                  key={label}
                  onClick={() => setVariant(v)}
                  className={cn(
                    "flex-1 rounded-xl border px-3 py-2 transition-colors",
                    variant === v
                      ? "border-teal-400 bg-teal-50 font-semibold text-teal-700 dark:bg-teal-900/30 dark:text-teal-300"
                      : "border-gray-200 text-gray-500 dark:border-gray-600",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[11px] text-gray-400">
              {variant
                ? "Tweak a few settings for this run only — nothing is saved to the agent."
                : saved
                  ? configLabel(saved)
                  : "…"}
            </p>
          </div>

          {variant && (
            <div className="grid grid-cols-2 gap-3 rounded-xl border border-dashed border-gray-200 p-3 dark:border-gray-600">
              <div>
                <Label htmlFor="v-provider">Provider</Label>
                <Select
                  id="v-provider"
                  value={o.provider}
                  onChange={(e) => setO({ ...o, provider: e.target.value as LlmProvider | "", model: "" })}
                >
                  <option value="">unchanged</option>
                  {providers.map((p) => (
                    <option key={p.provider} value={p.provider} disabled={!p.available}>
                      {p.provider}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="v-model">Model</Label>
                <Input
                  id="v-model"
                  list="v-models"
                  value={o.model}
                  placeholder="unchanged"
                  onChange={(e) => setO({ ...o, model: e.target.value })}
                />
                <datalist id="v-models">
                  {providerModels.map((m) => (
                    <option key={m} value={m} />
                  ))}
                </datalist>
              </div>
              <div>
                <Label htmlFor="v-topk">Results per search</Label>
                <Input id="v-topk" type="number" min={1} max={50} placeholder="unchanged" value={o.top_k}
                  onChange={(e) => setO({ ...o, top_k: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="v-iter">Max tool rounds</Label>
                <Input id="v-iter" type="number" min={1} max={10} placeholder="unchanged" value={o.max_iterations}
                  onChange={(e) => setO({ ...o, max_iterations: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="v-pipeline">Pipeline</Label>
                <Select id="v-pipeline" value={o.pipeline_id} onChange={(e) => setO({ ...o, pipeline_id: e.target.value })}>
                  <option value="">unchanged</option>
                  <option value="builtin">built-in</option>
                  {pipelines.filter((p) => p.status === "active").map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="v-mode">Retrieval mode</Label>
                <Select id="v-mode" value={o.default_retrieval_mode}
                  onChange={(e) => setO({ ...o, default_retrieval_mode: e.target.value as RetrievalMode | "" })}>
                  <option value="">unchanged</option>
                  <option value="auto">auto</option>
                  <option value="on">on</option>
                  <option value="off">off</option>
                </Select>
              </div>
            </div>
          )}
        </div>

        <div>
          <Label>Questions ({cases.filter((c) => c.question.trim()).length}/30)</Label>
          <p className="mb-2 text-[11px] text-gray-400">
            Optional per question: facts a correct answer must state (checks the answer itself), and the document it
            must come from (checks retrieval). Every question is graded for groundedness either way.
          </p>
          <div className="max-h-80 space-y-1.5 overflow-y-auto pr-1">
            {cases.map((c, i) => (
              <div key={i} className="flex gap-1.5">
                <Input
                  value={c.question}
                  placeholder={`Question ${i + 1}`}
                  onChange={(e) => setCase(i, { question: e.target.value })}
                />
                <KeywordsInput
                  value={c.expected_keywords ?? []}
                  onChange={(expected_keywords) => setCase(i, { expected_keywords })}
                />
                <Select
                  className="w-44 shrink-0"
                  value={c.expected_document_id ?? ""}
                  onChange={(e) => setCase(i, { expected_document_id: e.target.value ? Number(e.target.value) : null })}
                >
                  <option value="">any document</option>
                  {documents.map((d) => (
                    <option key={d.id} value={d.id}>{d.title}</option>
                  ))}
                </Select>
                <Button variant="secondary" size="sm" onClick={() => setCases((cs) => cs.filter((_, j) => j !== i))}>
                  ✕
                </Button>
              </div>
            ))}
          </div>
          {cases.length < 30 && (
            <Button
              className="mt-2"
              variant="secondary"
              size="sm"
              onClick={() => setCases((cs) => [...cs, { question: "", expected_document_id: null }])}
            >
              + Add question
            </Button>
          )}
        </div>
      </div>

      <div className="mt-5 flex items-center justify-end gap-3 border-t pt-4 dark:border-gray-700">
        <p className="text-[11px] text-gray-400">Runs in the background — each question goes through the full agent.</p>
        <Button disabled={!ready || create.isPending} onClick={() => create.mutate()}>
          {create.isPending ? "Starting…" : "Run evaluation"}
        </Button>
      </div>
    </Card>
  );
}

// ── User feedback ────────────────────────────────────────────────────────────

type FeedbackFilter = "all" | "down" | "up";

/**
 * Answers users rated in their own chats — one row per rated answer, each with
 * its own 👍 or 👎. Not a like counter on a single item: the summary counts
 * how many answers, across how many chats, went each way.
 *
 * Thumbs-down answers are the raw material for evaluations: pick some and they
 * become a question set, so a fix is measured against exactly what failed.
 */
function FeedbackPanel({ agentId, onEvaluate }: { agentId: number; onEvaluate: (cases: EvalCase[]) => void }) {
  const { data } = useQuery({ queryKey: ["feedback", agentId], queryFn: () => FeedbackApi.list(agentId) });
  const [filter, setFilter] = useState<FeedbackFilter>("down");
  const [picked, setPicked] = useState<number[]>([]);
  const [open, setOpen] = useState<number | null>(null);
  if (!data) return null;

  const total = data.up + data.down;
  const chats = new Set(data.items.map((i) => i.session_id)).size;
  const shown = data.items.filter((i) => filter === "all" || (filter === "down" ? i.rating === -1 : i.rating === 1));
  const toggle = (id: number) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const pickedItems = data.items.filter((i) => picked.includes(i.id));

  const tabs: { key: FeedbackFilter; label: string; count: number }[] = [
    { key: "down", label: "👎 Not helpful", count: data.down },
    { key: "up", label: "👍 Helpful", count: data.up },
    { key: "all", label: "All", count: total },
  ];

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-[#2D3748] dark:text-gray-100">Rated answers</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {total === 0
              ? "No answers rated yet. Users rate answers in their own chats with 👍 / 👎."
              : `${total} answer${total === 1 ? "" : "s"} rated across ${chats} chat${chats === 1 ? "" : "s"} — each row is one answer in one user's chat.`}
          </p>
        </div>
        {total > 0 && (
          // Share of rated answers each way — a proportion bar, not a vote tally.
          <div className="w-48">
            <div className="flex h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
              <div className="bg-teal-400" style={{ width: `${(data.up / total) * 100}%` }} />
              <div className="bg-rose-400" style={{ width: `${(data.down / total) * 100}%` }} />
            </div>
            <p className="mt-1 text-right text-[10px] text-gray-400">
              {Math.round((data.up / total) * 100)}% of rated answers helpful
            </p>
          </div>
        )}
      </div>

      {total > 0 && (
        <>
          <div className="mt-4 flex gap-1 text-xs">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setFilter(t.key)}
                className={cn(
                  "rounded-lg px-2.5 py-1 transition-colors",
                  filter === t.key
                    ? "bg-gray-100 font-semibold text-gray-800 dark:bg-gray-700 dark:text-gray-100"
                    : "text-gray-500 hover:text-gray-700 dark:text-gray-400",
                )}
              >
                {t.label} <span className="font-mono text-gray-400">{t.count}</span>
              </button>
            ))}
          </div>

          {shown.length === 0 ? (
            <p className="mt-3 text-xs text-gray-400">Nothing here.</p>
          ) : (
            <div className="mt-2 divide-y rounded-xl border dark:divide-gray-700 dark:border-gray-700">
              {shown.map((item) => (
                <div key={item.id} className="px-3 py-2.5 text-xs">
                  <div className="flex items-start gap-2.5">
                    <input
                      type="checkbox"
                      className="mt-1 accent-rose-500"
                      title="Add to an evaluation"
                      checked={picked.includes(item.id)}
                      onChange={() => toggle(item.id)}
                    />
                    <span
                      className={cn(
                        "mt-0.5 shrink-0 rounded-md px-1.5 py-0.5 text-[11px]",
                        item.rating === 1 ? "bg-teal-50 dark:bg-teal-900/30" : "bg-rose-50 dark:bg-rose-900/30",
                      )}
                      title={item.rating === 1 ? "Rated helpful" : "Rated not helpful"}
                    >
                      {item.rating === 1 ? "👍" : "👎"}
                    </span>
                    <button className="min-w-0 flex-1 text-left" onClick={() => setOpen(open === item.id ? null : item.id)}>
                      <p className="font-medium text-gray-800 dark:text-gray-100">{item.question}</p>
                      {item.query && item.query !== item.question && (
                        <p className="mt-0.5 text-[11px] text-gray-500 dark:text-gray-400">→ searched as “{item.query}”</p>
                      )}
                      {open !== item.id && (
                        <p className="mt-0.5 truncate text-gray-500 dark:text-gray-400">{item.answer}</p>
                      )}
                      {item.comment && (
                        <p className={cn("mt-0.5", item.rating === 1 ? "text-teal-600" : "text-rose-500")}>
                          “{item.comment}”
                        </p>
                      )}
                      <p className="mt-0.5 text-[10px] text-gray-400">
                        {item.user_email} · {item.session_title ?? `chat #${item.session_id}`} · answer{" "}
                        {item.turn_index + 1} · {new Date(item.created_at).toLocaleString()}
                      </p>
                    </button>
                  </div>
                  {open === item.id && (
                    <p className="ml-14 mt-2 whitespace-pre-wrap rounded-lg bg-gray-50 p-2 text-[11px] leading-relaxed text-gray-600 dark:bg-gray-700/40 dark:text-gray-300">
                      {item.answer}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="mt-3 flex items-center justify-between">
            <p className="text-[11px] text-gray-400">
              {picked.length ? `${picked.length} selected` : "Select answers to re-test them in an evaluation."}
            </p>
            <Button
              size="sm"
              disabled={picked.length === 0}
              // The standalone rewrite when there is one: a follow-up like
              // "그럼 마감은?" means nothing as a case of its own.
              onClick={() =>
                onEvaluate(pickedItems.map((i) => ({ question: i.query ?? i.question, expected_document_id: null })))
              }
            >
              Evaluate {picked.length || ""} selected
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}

// ── Unanswered questions ─────────────────────────────────────────────────────

/**
 * Questions the agent searched for but answered without citing a single
 * passage — usually "the documents don't cover this". Read as a to-do list:
 * documents to add to the agent's sets, or questions retrieval should have
 * found. Unlike ratings, these need no user to click anything.
 */
function UnansweredPanel({ agentId, onEvaluate }: { agentId: number; onEvaluate: (cases: EvalCase[]) => void }) {
  const { data } = useQuery({ queryKey: ["unanswered", agentId], queryFn: () => FeedbackApi.unanswered(agentId) });
  const [picked, setPicked] = useState<string[]>([]);
  if (!data) return null;

  const key = (i: UnansweredItem) => `${i.session_id}:${i.turn_index}`;
  const toggle = (k: string) => setPicked((p) => (p.includes(k) ? p.filter((x) => x !== k) : [...p, k]));
  const share = data.searched ? Math.round((data.unanswered / data.searched) * 100) : 0;

  return (
    <Card className="p-5">
      <h2 className="text-sm font-bold text-[#2D3748] dark:text-gray-100">Unanswered questions</h2>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        {data.searched === 0
          ? "No chat questions logged yet."
          : `${data.unanswered} of ${data.searched} questions that searched the documents (${share}%) were answered without citing any passage — usually because the documents don't cover them.`}
      </p>

      {data.items.length > 0 && (
        <>
          <div className="mt-3 divide-y rounded-xl border dark:divide-gray-700 dark:border-gray-700">
            {data.items.map((item) => (
              <label key={key(item)} className="flex cursor-pointer items-start gap-2.5 px-3 py-2.5 text-xs">
                <input
                  type="checkbox"
                  className="mt-1 accent-amber-500"
                  title="Add to an evaluation"
                  checked={picked.includes(key(item))}
                  onChange={() => toggle(key(item))}
                />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium text-gray-800 dark:text-gray-100">{item.question}</span>
                  {item.query !== item.question && (
                    <span className="mt-0.5 block text-[11px] text-gray-500 dark:text-gray-400">
                      → searched as “{item.query}”
                    </span>
                  )}
                  <span className="mt-0.5 block text-[10px] text-gray-400">
                    {item.user_email} · {item.session_title ?? `chat #${item.session_id}`} · {item.route ?? "agent"} ·{" "}
                    {item.source_count} passage{item.source_count === 1 ? "" : "s"} found, none cited ·{" "}
                    {new Date(item.created_at).toLocaleString()}
                  </span>
                </span>
              </label>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between">
            <p className="text-[11px] text-gray-400">
              {picked.length ? `${picked.length} selected` : "Select questions to re-test them after adding documents."}
            </p>
            <Button
              size="sm"
              disabled={picked.length === 0}
              onClick={() =>
                onEvaluate(
                  data.items
                    .filter((i) => picked.includes(key(i)))
                    .map((i) => ({ question: i.query, expected_document_id: null })),
                )
              }
            >
              Evaluate {picked.length || ""} selected
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

function StatusBadge({ run }: { run: EvalRun }) {
  if (run.status === "done") return <Badge tone="green">done</Badge>;
  if (run.status === "failed") return <Badge tone="red">failed</Badge>;
  return (
    <Badge tone="amber">
      <span className="animate-pulse">
        {run.status} {run.results.length}/{run.cases.length}
      </span>
    </Badge>
  );
}

export default function EvalPage() {
  const { agent } = useWorkspace();
  const qc = useQueryClient();
  const agentId = agent?.id;

  const { data: runs = [] } = useQuery({
    queryKey: ["evals", agentId],
    queryFn: () => EvalsApi.list(agentId!),
    enabled: agentId != null,
    // Poll only while something is still running.
    refetchInterval: (q) =>
      (q.state.data ?? []).some((r) => r.status === "pending" || r.status === "running") ? 2000 : false,
  });
  const { data: docs } = useQuery({
    // Expected documents come from the agent's workspace; the API caps a page at 200.
    queryKey: ["documents-all", agent?.workspace_id],
    queryFn: () => DocumentsApi.list(agent!.workspace_id, { limit: 200 }),
    enabled: agent != null,
  });
  const documents = docs?.items ?? [];
  const docTitle = (id: number | null) =>
    id == null ? "any" : documents.find((d) => d.id === id)?.title ?? `#${id}`;

  const [selected, setSelected] = useState<number[]>([]);
  const [creating, setCreating] = useState(false);
  // Questions handed over from the feedback panel, if that's how we got here.
  const [seedCases, setSeedCases] = useState<EvalCase[] | undefined>(undefined);

  // Default to the newest run when nothing is chosen.
  const shown = useMemo(() => {
    const ids = selected.length ? selected : runs[0] ? [runs[0].id] : [];
    return ids.map((id) => runs.find((r) => r.id === id)).filter((r): r is EvalRun => !!r);
  }, [selected, runs]);

  const remove = useMutation({
    mutationFn: (runId: number) => EvalsApi.remove(agentId!, runId),
    onSuccess: (_, runId) => {
      setSelected((s) => s.filter((id) => id !== runId));
      qc.invalidateQueries({ queryKey: ["evals", agentId] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to delete"),
  });

  const toggle = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-2)));

  // Questions picked from feedback or the unanswered list open a new evaluation.
  const evaluateCases = (cases: EvalCase[]) => {
    setSeedCases(cases);
    setCreating(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (!agent) return <Card className="p-8 text-sm text-gray-500">Select an agent first.</Card>;

  return (
    <div className="mx-auto max-w-7xl space-y-5 pb-16">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[#2D3748] dark:text-gray-100">Evaluate {agent.name}</h1>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Run a question set through the agent and measure retrieval, groundedness, speed and cost. Select two runs
            to compare them.
          </p>
        </div>
        {!creating && (
          <Button
            onClick={() => {
              setSeedCases(undefined);
              setCreating(true);
            }}
          >
            + New evaluation
          </Button>
        )}
      </div>

      {!creating && (
        <div className="grid gap-5 xl:grid-cols-2">
          <FeedbackPanel agentId={agent.id} onEvaluate={evaluateCases} />
          <UnansweredPanel agentId={agent.id} onEvaluate={evaluateCases} />
        </div>
      )}

      {creating && (
        <NewEvalPanel
          agentId={agent.id}
          workspaceId={agent.workspace_id}
          runs={runs}
          documents={documents}
          initialCases={seedCases}
          onClose={() => setCreating(false)}
          onCreated={(run) => {
            setCreating(false);
            setSeedCases(undefined);
            qc.invalidateQueries({ queryKey: ["evals", agentId] });
            setSelected((s) => [...s, run.id].slice(-2));
          }}
        />
      )}

      {runs.length === 0 && !creating ? (
        <Card className="p-10 text-center text-sm text-gray-500 dark:text-gray-400">
          No evaluations yet. Start one to get a baseline, then change a setting and run it again to compare.
        </Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
          {/* Runs */}
          <Card className="h-fit p-2">
            {runs.map((run) => {
              const idx = shown.findIndex((r) => r.id === run.id);
              return (
                <div
                  key={run.id}
                  onClick={() => toggle(run.id)}
                  className={cn(
                    "group cursor-pointer rounded-xl border-2 px-3 py-2.5 transition-colors",
                    idx >= 0 ? "bg-gray-50 dark:bg-gray-700/40" : "border-transparent hover:bg-gray-50 dark:hover:bg-gray-700/30",
                  )}
                  style={idx >= 0 ? { borderColor: RUN_COLORS[idx] } : undefined}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-semibold text-gray-800 dark:text-gray-100">{run.name}</span>
                    <StatusBadge run={run} />
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-gray-400">{configLabel(run.config_snapshot)}</p>
                  {run.prompt_name && (
                    <p className="truncate text-[11px] text-gray-400">prompt: {run.prompt_name}</p>
                  )}
                  <div className="mt-1 flex items-center justify-between text-[11px] text-gray-500">
                    <span>
                      hit {fmtPct(run.summary?.hit_rate ?? null)} · ground {fmtNum(run.summary?.avg_groundedness ?? null, 1)}
                    </span>
                    {run.status !== "running" && run.status !== "pending" && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          remove.mutate(run.id);
                        }}
                        className="text-gray-300 opacity-0 hover:text-rose-500 group-hover:opacity-100"
                      >
                        delete
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </Card>

          {/* Comparison */}
          {shown.length > 0 && (
            <div className="min-w-0 space-y-4">
              {shown.length === 2 && (
                <p className="text-xs text-gray-500">
                  Comparing <b style={{ color: RUN_COLORS[0] }}>{shown[0].name}</b> →{" "}
                  <b style={{ color: RUN_COLORS[1] }}>{shown[1].name}</b>. Arrows show whether B improved on A.
                </p>
              )}
              {shown.some((r) => r.error) && (
                <Card className="p-3 text-xs text-rose-500">{shown.find((r) => r.error)?.error}</Card>
              )}
              <MetricCards runs={shown} />
              <CaseTable runs={shown} docTitle={docTitle} />
              {shown[0].summary && (
                <p className="text-[10px] text-gray-400">
                  Groundedness judged by {shown[0].summary.judge_model} for every run, so scores stay comparable across
                  models.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
