import { useCallback, useRef, useState, useEffect, type KeyboardEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { SessionsApi, SystemPromptsApi } from "@/api/endpoints";
import { useWorkspace } from "@/workspace/WorkspaceProvider";
import { useAuth } from "@/auth/AuthProvider";
import { Button, Card, Textarea, Badge } from "@/components/ui";
import { cn } from "@/lib/cn";
import type { AgentCard, AgentRouteType, AgentStep, ChatRole, ChatSession, ChatTurn, GraphTopology, McpAction, NodeStatus, PendingApproval, Rating, RetrievalMode, SourceItem, SystemPrompt, TraceSpan } from "@/api/types";
import { CitedMarkdown } from "@/components/chat/CitedMarkdown";
import { RunInspector, type RunState } from "@/components/chat/RunInspector";
import { getAgentTheme } from "@/lib/agentTheme";
import { isSubmitEnter } from "@/lib/keys";
import type { ChatLaunchState } from "@/pages/AgentHomePage";

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

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" />
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

function PencilIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5">
      <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" />
    </svg>
  );
}

function RetryIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5">
      <path d="M17.65 6.35A7.96 7.96 0 0 0 12 4a8 8 0 1 0 7.73 10h-2.08A6 6 0 1 1 12 6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" />
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

// ── Agent flow diagram ────────────────────────────────────────────────────────

const AGENT_LABELS: Record<AgentRouteType, string> = {
  retrieval: "Retrieval",
  summary: "Summary",
  comparison: "Comparison",
};

const AGENT_ACTIVE_CLS: Record<AgentRouteType, string> = {
  retrieval: "border-teal-400 bg-teal-50 text-teal-700 dark:border-teal-600 dark:bg-teal-900/40 dark:text-teal-300",
  summary: "border-blue-400 bg-blue-50 text-blue-700 dark:border-blue-600 dark:bg-blue-900/40 dark:text-blue-300",
  comparison: "border-purple-400 bg-purple-50 text-purple-700 dark:border-purple-600 dark:bg-purple-900/40 dark:text-purple-300",
};

const AGENT_BADGE_CLS: Record<AgentRouteType, string> = {
  retrieval: "text-teal-600 dark:text-teal-400",
  summary: "text-blue-600 dark:text-blue-400",
  comparison: "text-purple-600 dark:text-purple-400",
};

function FlowArrow() {
  return <span className="text-gray-300 dark:text-gray-600 select-none">→</span>;
}

function AgentFlowDiagram({
  agentRoute,
  isSearching,
  hasToolCalls,
}: {
  agentRoute?: AgentRouteType;
  isSearching: boolean;
  hasToolCalls: boolean;
}) {
  const agents: AgentRouteType[] = ["retrieval", "summary", "comparison"];

  return (
    <div className="mb-2 flex flex-wrap items-center gap-1 text-[11px]">
      <span className="rounded-full border border-gray-200 px-2 py-0.5 text-gray-400 dark:border-gray-600 dark:text-gray-500">
        Start
      </span>
      <FlowArrow />
      <span
        className={cn(
          "rounded border px-2 py-0.5 transition-colors",
          !agentRoute
            ? "animate-pulse border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-600 dark:bg-amber-900/30 dark:text-amber-300"
            : "border-gray-200 bg-gray-50 text-gray-500 dark:border-gray-600 dark:bg-gray-700/40 dark:text-gray-400",
        )}
      >
        Supervisor
      </span>
      <FlowArrow />
      <div className="flex items-center gap-1">
        {agents.map((a) => {
          const isActive = agentRoute === a && hasToolCalls;
          return (
            <span
              key={a}
              className={cn(
                "rounded border px-2 py-0.5 transition-all",
                isActive
                  ? cn(AGENT_ACTIVE_CLS[a], isSearching && "animate-pulse")
                  : "border-gray-100 text-gray-300 dark:border-gray-700 dark:text-gray-600",
              )}
            >
              {AGENT_LABELS[a]}
            </span>
          );
        })}
      </div>
      <FlowArrow />
      <span className="rounded-full border border-gray-100 px-2 py-0.5 text-gray-300 dark:border-gray-700 dark:text-gray-600">
        End
      </span>
    </div>
  );
}

// ── Agent route badge ────────────────────────────────────────────────────────

const AGENT_DOT_CLS: Record<AgentRouteType, string> = {
  retrieval: "bg-teal-400 dark:bg-teal-500",
  summary: "bg-blue-400 dark:bg-blue-500",
  comparison: "bg-purple-400 dark:bg-purple-500",
};

function AgentRouteBadge({ agentRoute, isActive = false }: { agentRoute: AgentRouteType; isActive?: boolean }) {
  return (
    <div className="mb-1.5 flex items-center gap-1.5 text-[10px]">
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          AGENT_DOT_CLS[agentRoute],
          isActive && "animate-pulse",
        )}
      />
      <span className="text-gray-400 dark:text-gray-500">
        via{" "}
        <span className={cn(AGENT_BADGE_CLS[agentRoute], isActive && "font-medium")}>
          {AGENT_LABELS[agentRoute]} Agent
        </span>
        {isActive && (
          <span className="ml-1 italic text-gray-300 dark:text-gray-600">running…</span>
        )}
      </span>
    </div>
  );
}

// ── Streaming status label ────────────────────────────────────────────────────

function StreamingStatus({ turn }: { turn: ChatTurn }) {
  if (!turn.isStreaming || turn.content) return null;

  let text: string;
  if (!turn.agentRoute) {
    text = "Supervisor routing…";
  } else {
    const lastStep = turn.agentSteps[turn.agentSteps.length - 1];
    if (!lastStep) {
      text = `${AGENT_LABELS[turn.agentRoute]} Agent preparing…`;
    } else if (lastStep.type === "tool_call") {
      text = `Searching: "${lastStep.input}"`;
    } else {
      text = `${AGENT_LABELS[turn.agentRoute]} Agent generating…`;
    }
  }

  return (
    <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500">
      <span className="inline-flex gap-1">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-300 [animation-delay:-0.3s] dark:bg-gray-600" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-300 [animation-delay:-0.15s] dark:bg-gray-600" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-300 dark:bg-gray-600" />
      </span>
      <span className="italic">{text}</span>
    </div>
  );
}

// ── Score bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(Math.round(score * 100), 100);
  return (
    <span className="inline-flex items-center gap-1.5 shrink-0">
      <span className="h-1.5 w-12 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-600">
        <span
          className="block h-full rounded-full bg-teal-400 dark:bg-teal-500"
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="font-mono text-[10px] tabular-nums">
        {score < 0.01 ? score.toExponential(2) : score.toFixed(3)}
      </span>
    </span>
  );
}

// ── Source card ───────────────────────────────────────────────────────────────

function SourceCard({ source }: { source: SourceItem }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="cursor-pointer rounded-lg border border-gray-100 bg-gray-50 px-3 py-1.5 text-xs transition-colors hover:border-gray-200 dark:border-gray-700 dark:bg-gray-700/40 dark:hover:border-gray-600"
      onClick={() => setExpanded((p) => !p)}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center min-w-0">
          <span className="mr-2 shrink-0 font-mono text-teal-500">[{source.index}]</span>
          <span className="truncate font-medium text-gray-700 dark:text-gray-200">
            {source.title ?? `Document #${source.document_id}`}
          </span>
        </div>
        <ScoreBar score={source.score} />
      </div>
      {expanded && source.snippet && (
        <p className="mt-1.5 border-t border-gray-100 pt-1.5 leading-relaxed text-gray-500 dark:border-gray-700 dark:text-gray-400">
          {source.snippet}
        </p>
      )}
    </div>
  );
}

// ── Agent steps ───────────────────────────────────────────────────────────────

function AgentSteps({ steps }: { steps: AgentStep[] }) {
  const [open, setOpen] = useState(false);
  if (steps.length === 0) return null;

  const searching = steps[steps.length - 1].type === "tool_call";
  const completedToolCalls = steps.filter((s) => s.type === "tool_call").length;
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
        {searching ? (
          <span className="animate-pulse">
            {completedToolCalls} search{completedToolCalls !== 1 ? "es" : ""} · searching…
          </span>
        ) : (
          <span>
            {completedToolCalls} search{completedToolCalls !== 1 ? "es" : ""} · {totalSources} source
            {totalSources !== 1 ? "s" : ""} found
          </span>
        )}
      </button>
      {open && (
        <div className="border-t border-gray-100 px-3 py-2 space-y-2 dark:border-gray-700">
          {steps.map((step, i) => {
            const isPending = step.type === "tool_call" && i === steps.length - 1 && searching;
            return (
              <div key={i} className="flex gap-2">
                {step.type === "tool_call" ? (
                  <>
                    <span className={cn(step.delegate ? "text-rose-500" : "text-teal-500", isPending && "animate-pulse")}>
                      {step.delegate ? "🤝" : "🔍"}
                    </span>
                    <span className="text-gray-600 dark:text-gray-300">
                      {step.delegate ? (
                        <>
                          Asking <span className="font-semibold">{step.tool}</span> agent:{" "}
                        </>
                      ) : (
                        "Searching: "
                      )}
                      <span className="font-mono">{step.input}</span>
                      {isPending && <span className="ml-1 animate-pulse text-gray-400">…</span>}
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-blue-400">📄</span>
                    <span className="text-gray-500 dark:text-gray-400">
                      {step.delegate ? `${step.tool} answered from ` : "Found "}
                      {step.output?.length ?? 0} {step.delegate ? "source" : "result"}
                      {(step.output?.length ?? 0) !== 1 ? "s" : ""}
                    </span>
                  </>
                )}
              </div>
            );
          })}
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
        <SourceCard key={s.index} source={s} />
      ))}
    </div>
  );
}

// ── Message bubble ───────────────────────────────────────────────────────────

// ── Answer feedback ──────────────────────────────────────────────────────────

function AnswerFeedback({
  feedback,
  onRate,
}: {
  feedback: ChatTurn["feedback"];
  onRate: (rating: Rating | null, comment?: string | null) => void;
}) {
  const [draft, setDraft] = useState(feedback?.comment ?? "");
  const [editing, setEditing] = useState(false);
  const rating = feedback?.rating ?? null;

  const choose = (r: Rating) => {
    // Clicking the current rating again takes it back.
    if (rating === r) {
      onRate(null);
      setEditing(false);
      return;
    }
    onRate(r, r === -1 ? null : undefined);
    // A thumbs-down is most useful with a reason, so offer the box right away.
    setEditing(r === -1);
  };

  const btn = (r: Rating, label: string, title: string) => (
    <button
      type="button"
      title={title}
      onClick={() => choose(r)}
      className={cn(
        "rounded-md px-1.5 py-0.5 text-xs transition-colors",
        rating === r
          ? r === 1
            ? "bg-teal-50 text-teal-600 dark:bg-teal-900/40 dark:text-teal-300"
            : "bg-rose-50 text-rose-600 dark:bg-rose-900/40 dark:text-rose-300"
          : "text-gray-300 hover:bg-gray-100 hover:text-gray-500 dark:text-gray-500 dark:hover:bg-gray-700",
      )}
    >
      {label}
    </button>
  );

  return (
    <div className="mt-1.5">
      <div className="flex items-center gap-0.5">
        {btn(1, "👍", "Helpful")}
        {btn(-1, "👎", "Not helpful")}
        {rating === -1 && !editing && (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="ml-1 truncate text-[11px] text-gray-400 hover:text-gray-600"
          >
            {feedback?.comment ? `“${feedback.comment}”` : "Add a reason"}
          </button>
        )}
      </div>
      {editing && (
        <div className="mt-1.5 flex gap-1.5">
          <input
            autoFocus
            value={draft}
            maxLength={1000}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (isSubmitEnter(e)) {
                onRate(-1, draft.trim() || null);
                setEditing(false);
              }
            }}
            placeholder="What was wrong? (optional — helps tune the agent)"
            className="flex-1 rounded-lg border border-gray-200 px-2 py-1 text-xs focus:border-rose-300 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
          />
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              onRate(-1, draft.trim() || null);
              setEditing(false);
            }}
          >
            Save
          </Button>
        </div>
      )}
    </div>
  );
}

function EditQuestion({ initial, onSave, onCancel }: { initial: string; onSave: (text: string) => void; onCancel: () => void }) {
  const [draft, setDraft] = useState(initial);
  const save = () => draft.trim() && onSave(draft.trim());
  return (
    <div className="w-full min-w-[280px] rounded-2xl border border-teal-200 bg-white p-2 dark:border-teal-800 dark:bg-gray-800">
      <Textarea
        autoFocus
        rows={3}
        className="resize-none text-sm"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (isSubmitEnter(e) && !e.shiftKey) {
            e.preventDefault();
            save();
          } else if (e.key === "Escape") onCancel();
        }}
      />
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-[10px] text-gray-400">Answers after this question will be replaced.</span>
        <span className="flex gap-1.5">
          <Button size="sm" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button size="sm" disabled={!draft.trim()} onClick={save}>
            Send
          </Button>
        </span>
      </div>
    </div>
  );
}

function MessageBubble({
  turn,
  onRate,
  onEdit,
  onRegenerate,
  onDecide,
  busy = false,
}: {
  turn: ChatTurn;
  /** Approve or reject an MCP call this turn is paused on. */
  onDecide?: (callId: number, approve: boolean, args?: Record<string, unknown>) => void;
  /** Something is streaming: decisions wait. */
  busy?: boolean;
  /** Present when this answer can be rated (finished, saved in a session). */
  onRate?: (rating: Rating | null, comment?: string | null) => void;
  /** User messages: resend this question reworded, replacing what followed it. */
  onEdit?: (text: string) => void;
  /** The latest answer: ask its question again for a fresh answer. */
  onRegenerate?: () => void;
}) {
  const isUser = turn.role === "user";
  const [editing, setEditing] = useState(false);
  if (isUser && editing && onEdit) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%]">
          <EditQuestion
            initial={turn.content}
            onCancel={() => setEditing(false)}
            onSave={(text) => {
              setEditing(false);
              onEdit(text);
            }}
          />
        </div>
      </div>
    );
  }
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("group max-w-[80%]", isUser ? "order-2" : "order-1")}>
        {!isUser && turn.isStreaming && !turn.agentRoute && (
          <AgentFlowDiagram
            agentRoute={turn.agentRoute}
            isSearching={!turn.content}
            hasToolCalls={turn.agentSteps.some((s) => s.type === "tool_call")}
          />
        )}
        {!isUser && turn.agentRoute && (
          <AgentRouteBadge agentRoute={turn.agentRoute} isActive={turn.isStreaming} />
        )}
        {!isUser && <AgentSteps steps={turn.agentSteps} />}
        {!isUser && turn.actions && turn.actions.length > 0 && <McpActions actions={turn.actions} />}
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
            <StreamingStatus turn={turn} />
          ) : turn.approvals?.length && !turn.content ? (
            <p className="text-gray-500 dark:text-gray-400">
              {turn.approvals.length === 1 ? "This action needs" : "These actions need"} your approval before I continue.
            </p>
          ) : turn.error ? (
            <p className="text-red-500">{turn.error}</p>
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <CitedMarkdown content={turn.content} sources={turn.sources} />
            </div>
          )}
        </div>
        {isUser && onEdit && (
          <div className="mt-1 flex justify-end transition-opacity md:opacity-0 md:group-hover:opacity-100 md:focus-within:opacity-100">
            <button
              onClick={() => setEditing(true)}
              title="Edit this question and ask again"
              className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700"
            >
              <PencilIcon /> Edit
            </button>
          </div>
        )}
        {!isUser &&
          turn.approvals?.map((a) => (
            <ApprovalCard key={a.call_id} approval={a} busy={busy} onDecide={(ok, args) => onDecide?.(a.call_id, ok, args)} />
          ))}
        {!isUser && <Sources sources={turn.sources} />}
        {!isUser && (onRate || onRegenerate) && (
          <div className="flex flex-wrap items-start gap-2">
            {onRate && <AnswerFeedback feedback={turn.feedback} onRate={onRate} />}
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                title="Ask the same question again for a new answer"
                className="mt-1.5 flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700"
              >
                <RetryIcon /> Regenerate
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── MCP actions and approvals ────────────────────────────────────────────────

const ACTION_STATUS: Record<McpAction["status"], { label: string; cls: string }> = {
  running: { label: "running", cls: "text-amber-600 dark:text-amber-400 animate-pulse" },
  waiting: { label: "awaiting approval", cls: "text-violet-600 dark:text-violet-300" },
  done: { label: "done", cls: "text-teal-600 dark:text-teal-400" },
  error: { label: "failed", cls: "text-red-500" },
};

function formatArgs(args: Record<string, unknown>) {
  return Object.entries(args)
    .filter(([, v]) => v !== "" && v != null)
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
}

/** MCP tool calls in a turn — what the agent did outside the documents. */
function McpActions({ actions }: { actions: McpAction[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="mb-2 space-y-1 rounded-xl border border-violet-100 bg-violet-50/50 px-3 py-2 text-xs dark:border-violet-900/50 dark:bg-violet-900/10">
      {actions.map((a) => {
        const st = ACTION_STATUS[a.status];
        return (
          <div key={a.id}>
            <button
              onClick={() => setOpen(open === a.id ? null : a.id)}
              disabled={!a.output}
              className="flex w-full items-start gap-2 text-left disabled:cursor-default"
            >
              <span className="text-violet-500">⚙</span>
              <span className="min-w-0 flex-1 text-gray-600 dark:text-gray-300">
                <span className="font-semibold">{a.tool}</span>
                <span className="text-gray-400"> · {a.server}</span>
                {Object.keys(a.args).length > 0 && (
                  <span className="block truncate font-mono text-[11px] text-gray-400">{formatArgs(a.args)}</span>
                )}
              </span>
              <span className={cn("shrink-0 font-medium", st.cls)}>{st.label}</span>
            </button>
            {open === a.id && a.output && (
              <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-white p-2 font-mono text-[11px] text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                {a.output}
              </pre>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** A paused MCP call: show exactly what will run, let the user fix the arguments, then decide. */
function ApprovalCard({
  approval,
  busy,
  onDecide,
}: {
  approval: PendingApproval;
  busy: boolean;
  onDecide: (approve: boolean, args?: Record<string, unknown>) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => JSON.stringify(approval.args, null, 2));
  const [error, setError] = useState<string | null>(null);

  const approve = () => {
    if (!editing) return onDecide(true);
    try {
      const parsed = JSON.parse(draft);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) throw new Error("must be a JSON object");
      onDecide(true, parsed as Record<string, unknown>);
    } catch (e) {
      setError(`Arguments aren't valid JSON: ${(e as Error).message}`);
    }
  };

  return (
    <div className="mt-2 rounded-xl border border-violet-300 bg-white p-3 text-sm shadow-sm dark:border-violet-700 dark:bg-gray-800">
      <div className="mb-2 flex flex-wrap items-baseline gap-x-2">
        <span className="text-[10px] font-bold uppercase tracking-wider text-violet-600 dark:text-violet-300">
          Approval needed
        </span>
        <span className="font-semibold text-gray-800 dark:text-gray-100">{approval.title || approval.tool}</span>
        <span className="text-xs text-gray-400">
          {approval.server} · <span className="font-mono">{approval.tool}</span>
        </span>
      </div>
      {editing ? (
        <textarea
          id={`approval-args-${approval.call_id}`}
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            setError(null);
          }}
          rows={Math.min(12, draft.split("\n").length + 1)}
          className="w-full rounded-lg border border-gray-200 bg-gray-50 p-2 font-mono text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-violet-300 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200"
        />
      ) : (
        <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-1 rounded-lg bg-gray-50 p-2 text-xs dark:bg-gray-900">
          {Object.entries(approval.args).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="font-mono text-gray-400">{k}</dt>
              <dd className="break-words text-gray-700 dark:text-gray-200">
                {v === "" || v == null ? <span className="text-gray-300">—</span> : typeof v === "string" ? v : JSON.stringify(v)}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          onClick={approve}
          disabled={busy}
          className="rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-700 disabled:opacity-50"
        >
          {editing ? "Approve with changes" : "Approve"}
        </button>
        <button
          onClick={() => onDecide(false)}
          disabled={busy}
          className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
        >
          Reject
        </button>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            disabled={busy}
            className="ml-auto text-xs text-gray-400 hover:text-gray-600 disabled:opacity-50"
          >
            Edit arguments
          </button>
        )}
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
  onClose,
}: {
  sessions: ChatSession[];
  activeId: number | null;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  onNew: () => void;
  creating: boolean;
  disabled: boolean;
  onClose?: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 p-3 border-b border-gray-100 dark:border-gray-700">
        {onClose && (
          <button
            className="shrink-0 rounded-lg p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 md:hidden"
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        )}
        <Button
          size="sm"
          variant="secondary"
          className="flex flex-1 items-center justify-center gap-1.5"
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
              <span className="min-w-0 flex-1" title={session.title ?? undefined}>
                <span className="block truncate">{session.title ?? "New chat"}</span>
                <span className="block text-[10px] opacity-60">{formatSessionDate(session.updated_at)}</span>
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
  agentId,
  onClose,
  isAdmin,
}: {
  agentId: number;
  onClose: () => void;
  isAdmin: boolean;
}) {
  const qc = useQueryClient();
  const [newName, setNewName] = useState("");
  const [newContent, setNewContent] = useState("");
  const [creating, setCreating] = useState(false);

  const { data: prompts = [], isLoading } = useQuery({
    queryKey: ["system-prompts", agentId],
    queryFn: () => SystemPromptsApi.list(agentId),
  });

  const activate = useMutation({
    mutationFn: (id: number) => SystemPromptsApi.activate(agentId, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system-prompts", agentId] });
      toast.success("System prompt activated");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed"),
  });

  const remove = useMutation({
    mutationFn: (id: number) => SystemPromptsApi.remove(agentId, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system-prompts", agentId] });
      toast.success("Deleted");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed"),
  });

  const create = useMutation({
    mutationFn: () => SystemPromptsApi.create(agentId, { name: newName, content: newContent }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system-prompts", agentId] });
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

// ── Welcome (empty chat) ──────────────────────────────────────────────────────

function AgentWelcome({ agent, onAsk }: { agent: AgentCard; onAsk: (q: string) => void }) {
  const theme = getAgentTheme(agent);
  const { description, starter_questions } = agent.agent_config;
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-4 text-center">
      <span
        className="flex h-14 w-14 items-center justify-center rounded-2xl text-3xl text-white shadow-md"
        style={{ background: `linear-gradient(135deg, ${theme.gradientFrom}, ${theme.gradientTo})` }}
      >
        {theme.icon}
      </span>
      <div>
        <p className="text-base font-bold text-[#2D3748] dark:text-gray-100">{agent.name}</p>
        <p className="mt-1 max-w-md text-sm text-gray-500 dark:text-gray-400">
          {description || "Ask anything about this agent's documents."}
        </p>
      </div>
      {starter_questions.length > 0 && (
        <div className="flex max-w-xl flex-wrap justify-center gap-2">
          {starter_questions.map((q) => (
            <button
              key={q}
              onClick={() => onAsk(q)}
              className="rounded-xl border border-gray-200 px-3 py-1.5 text-xs text-gray-600 transition-colors hover:border-gray-300 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const EMPTY_RUN: RunState = { topology: null, nodeStatus: {}, delegateStates: {}, spans: [], runStartedAt: null };

// ── Main page ────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const { agent, agents, selectAgent } = useWorkspace();
  const { user } = useAuth();
  const qc = useQueryClient();

  // The open session, tagged with the agent it belongs to. When the agent
  // changes, effects run once before any reset lands; tagging makes the old
  // agent's session read as "none" in that render instead of being requested
  // under the new agent (a 404).
  const [activeSession, setActiveSession] = useState<{ agentId: number; id: number } | null>(null);
  const activeSessionId = activeSession && activeSession.agentId === agent?.id ? activeSession.id : null;
  const setActiveSessionId = useCallback(
    (id: number | null) => setActiveSession(id == null || !agent ? null : { agentId: agent.id, id }),
    [agent],
  );
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [showPrompts, setShowPrompts] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>(
    agent?.agent_config.default_retrieval_mode ?? "auto",
  );
  // Execution graph for the most recent run: its shape, plus where the run is.
  const [run, setRun] = useState<RunState>(EMPTY_RUN);
  const [showGraph, setShowGraph] = useState(true);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevAgentIdRef = useRef<number | null>(null);
  // A session sendMessage just created: empty on the server, so the
  // load-messages effect must not reload it over the turns being streamed in.
  const freshSessionRef = useRef<number | null>(null);
  // A starter question carried over from the landing page, sent once on arrival.
  const location = useLocation();
  const navigate = useNavigate();
  const launchPromptRef = useRef((location.state as ChatLaunchState | null)?.prompt ?? null);
  // While that question is being sent, don't auto-open the latest old session.
  const suppressAutoSelectRef = useRef(launchPromptRef.current != null);

  const isAdmin = user?.is_superadmin || false;

  const { data: prompts = [] } = useQuery({
    queryKey: ["system-prompts", agent?.id],
    queryFn: () => SystemPromptsApi.list(agent!.id),
    enabled: !!agent,
  });
  const activePrompt = prompts.find((p) => p.is_active);

  const { data: sessions = [], isSuccess: sessionsLoaded } = useQuery({
    queryKey: ["sessions", agent?.id],
    queryFn: () => SessionsApi.list(agent!.id),
    enabled: !!agent,
  });

  const createSession = useMutation({
    mutationFn: () => SessionsApi.create(agent!.id),
    onSuccess: (session) => {
      qc.invalidateQueries({ queryKey: ["sessions", agent?.id] });
      setActiveSessionId(session.id);
      setTurns([]);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to create session"),
  });

  const deleteSession = useMutation({
    mutationFn: (sessionId: number) => SessionsApi.remove(agent!.id, sessionId),
    onSuccess: (_, deletedId) => {
      qc.invalidateQueries({ queryKey: ["sessions", agent?.id] });
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

  // Reset when the agent changes
  useEffect(() => {
    if (!agent) return;
    if (agent.id === prevAgentIdRef.current) return;
    prevAgentIdRef.current = agent.id;
    setActiveSessionId(null);
    setTurns([]);
    setRetrievalMode(agent.agent_config.default_retrieval_mode);
  }, [agent?.id]);

  // Send the landing page's starter question once, in a fresh session.
  useEffect(() => {
    const prompt = launchPromptRef.current;
    if (!prompt || !agent) return;
    launchPromptRef.current = null;
    navigate(location.pathname, { replace: true, state: null }); // a reload must not resend it
    void sendMessage(prompt, { newSession: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent?.id]);

  // Lift the auto-select hold only once the new session is committed. Clearing
  // it right after creation races the session-list refetch: react-query renders
  // synchronously, before setActiveSessionId lands, and auto-select would see
  // "no session" and open the latest old one instead.
  useEffect(() => {
    if (activeSessionId != null) suppressAutoSelectRef.current = false;
  }, [activeSessionId]);

  // Auto-select first session once sessions load
  useEffect(() => {
    if (!sessionsLoaded || activeSessionId != null || suppressAutoSelectRef.current) return;
    if (sessions.length > 0) {
      setActiveSessionId(sessions[0].id);
    }
  }, [sessionsLoaded, sessions, activeSessionId]);

  // Load messages from DB when active session changes
  useEffect(() => {
    if (!agent || !activeSessionId) {
      setTurns([]);
      return;
    }
    if (freshSessionRef.current === activeSessionId) {
      freshSessionRef.current = null;
      setLoadingMessages(false);
      return;
    }

    let cancelled = false;
    setLoadingMessages(true);
    setTurns([]);

    Promise.all([SessionsApi.messages(agent.id, activeSessionId), SessionsApi.pendingApprovals(agent.id, activeSessionId)])
      .then(([messages, pending]) => {
        if (cancelled) return;
        const loaded: ChatTurn[] = messages.map((m) => ({
          id: crypto.randomUUID(),
          role: m.role as ChatRole,
          content: m.content,
          agentSteps: [],
          sources: m.sources ?? [],
          isStreaming: false,
          turnIndex: m.turn_index ?? undefined,
          feedback: m.feedback,
        }));
        // A turn paused on an approval has no answer yet: show it waiting.
        if (pending.length) {
          loaded.push({
            id: crypto.randomUUID(),
            role: "assistant",
            content: "",
            agentSteps: [],
            sources: [],
            isStreaming: false,
            approvals: pending.map((c) => ({ call_id: c.id, server: c.server_name, tool: c.tool, args: c.args })),
          });
        }
        setTurns(loaded);
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
  }, [activeSessionId, agent?.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function rateTurn(turnId: string, turnIndex: number, rating: Rating | null, comment?: string | null) {
    if (!agent || !activeSessionId) return;
    const before = turns.find((t) => t.id === turnId)?.feedback ?? null;
    const next = rating == null ? null : { rating, comment: comment === undefined ? (before?.comment ?? null) : comment };
    // Optimistic: the thumb lights up immediately, and reverts if the save fails.
    setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, turnIndex, feedback: next } : t)));
    try {
      if (next == null) await SessionsApi.clearRating(agent.id, activeSessionId, turnIndex);
      else await SessionsApi.rate(agent.id, activeSessionId, turnIndex, next.rating, next.comment);
    } catch (e) {
      setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, feedback: before } : t)));
      toast.error(e instanceof Error ? e.message : "Couldn't save your rating");
    }
  }

  /**
   * `replaceTurn` (0-based, counting user messages) reruns the session from that
   * question with `text` in its place — editing it, or (with `regenerate`, same
   * words) asking for a fresh answer, which the server writes a little warmer.
   */
  async function sendMessage(
    text?: string,
    opts: { newSession?: boolean; replaceTurn?: number; regenerate?: boolean } = {},
  ) {
    const query = (text ?? input).trim();
    if (!agent || !query || streaming) return;
    if (opts.replaceTurn == null && !opts.newSession && turns.some((t) => t.approvals?.length)) {
      toast.error("Approve or reject the pending action first");
      return;
    }
    if (opts.replaceTurn != null && activeSessionId == null) return;
    if (text === undefined) setInput("");
    setStreaming(true);

    // No session yet (first visit, or a starter question): make one rather than
    // asking the user to click "new chat" before they can type.
    let sessionId = opts.newSession ? null : activeSessionId;
    const isNewSession = sessionId == null;
    if (sessionId == null) {
      suppressAutoSelectRef.current = true;
      try {
        const session = await SessionsApi.create(agent.id);
        freshSessionRef.current = session.id;
        setActiveSessionId(session.id);
        qc.invalidateQueries({ queryKey: ["sessions", agent.id] });
        sessionId = session.id;
      } catch (e) {
        suppressAutoSelectRef.current = false;
        toast.error(e instanceof Error ? e.message : "Failed to create session");
        setStreaming(false);
        return;
      }
    }

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

    setTurns((prev) => {
      if (isNewSession) return [userTurn, assistantTurn];
      if (opts.replaceTurn == null) return [...prev, userTurn, assistantTurn];
      // Drop the replaced question and everything after it, as the server does.
      let users = -1;
      const cut = prev.findIndex((t) => t.role === "user" && ++users === opts.replaceTurn);
      return [...(cut < 0 ? prev : prev.slice(0, cut)), userTurn, assistantTurn];
    });
    // The graph is rebuilt per run, so clear the previous run's trace.
    setRun(EMPTY_RUN);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await consumeStream(
        SessionsApi.chat(
          agent.id,
          sessionId,
          query,
          undefined,
          ctrl.signal,
          retrievalMode,
          opts.replaceTurn,
          opts.regenerate,
        ),
        assistantId,
      );
    } finally {
      setStreaming(false);
      abortRef.current = null;
      qc.invalidateQueries({ queryKey: ["sessions", agent.id] });
    }
  }

  /**
   * Feed one run's SSE stream into the assistant turn `assistantId`. A resumed
   * run (after an approval) continues the same turn, so it starts from what
   * the turn already shows.
   */
  async function consumeStream(
    stream: AsyncGenerator<{ event: string; data: string }>,
    assistantId: string,
    from?: ChatTurn,
  ) {
    let steps: AgentStep[] = from?.agentSteps ?? [];
    let sources: SourceItem[] = from?.sources ?? [];
    let actions: McpAction[] = from?.actions ?? [];
    let content = "";
    let topology: GraphTopology | null = null;
    // Delegate tool name → agent name, for readable step labels.
    const delegateName = (tool: string) =>
      topology?.nodes.find((n) => n.id === `delegate:${tool.replace("ask_agent_", "")}`)?.label ?? tool;
    const patch = (fields: Partial<ChatTurn>) =>
      setTurns((prev) => prev.map((t) => (t.id === assistantId ? { ...t, ...fields } : t)));

    try {
      for await (const { event, data } of stream) {
        if (event === "graph") {
          topology = JSON.parse(data) as GraphTopology;
          const shape = topology;
          setRun({ ...EMPTY_RUN, topology: shape, runStartedAt: performance.now() });
        } else if (event === "node_state") {
          const payload = JSON.parse(data) as { node: string; status: NodeStatus };
          setRun((r) => ({ ...r, nodeStatus: { ...r.nodeStatus, [payload.node]: payload.status } }));
        } else if (event === "delegate_state") {
          const p = JSON.parse(data) as { delegate: string; node: string; status: NodeStatus };
          setRun((r) => ({
            ...r,
            delegateStates: {
              ...r.delegateStates,
              [p.delegate]: { ...(r.delegateStates[p.delegate] ?? {}), [p.node]: p.status },
            },
          }));
        } else if (event === "span") {
          const p = JSON.parse(data) as {
            id: string; parent_id: string | null; kind: TraceSpan["kind"]; name: string;
            phase: "start" | "end"; t_ms: number; meta: Record<string, unknown>;
          };
          setRun((r) => ({
            ...r,
            spans:
              p.phase === "start"
                ? [...r.spans, { id: p.id, parent_id: p.parent_id, kind: p.kind, name: p.name, start: p.t_ms, meta: p.meta }]
                : r.spans.map((sp) => (sp.id === p.id ? { ...sp, end: p.t_ms, meta: { ...sp.meta, ...p.meta } } : sp)),
          }));
        } else if (event === "supervisor_route") {
          const payload = JSON.parse(data) as { agent_type: AgentRouteType };
          patch({ agentRoute: payload.agent_type });
        } else if (event === "agent_step") {
          const payload = JSON.parse(data) as { type: string; tool: string; input?: string; output?: SourceItem[] };
          const isDelegate = payload.tool.startsWith("ask_agent_");
          const step: AgentStep = {
            type: payload.type as "tool_call" | "observation",
            tool: isDelegate ? delegateName(payload.tool) : payload.tool,
            delegate: isDelegate,
            input: payload.input,
            output: payload.output,
          };
          // A resumed run repeats the turn's opening search; don't list it twice.
          if (from && steps.some((s) => s.type === step.type && s.tool === step.tool && s.input === step.input)) continue;
          steps = [...steps, step];
          // A delegate's sources arrive renumbered into this answer's sequence,
          // so they join its citations like our own searches.
          if (payload.type === "observation" && payload.output) {
            sources = [...sources, ...payload.output];
          }
          // Text streamed before a tool call is the model narrating its plan
          // ("let me search…") — or a tool call it printed as text. The answer
          // starts after the last tool call, so drop it.
          if (payload.type === "tool_call") content = "";
          patch({ agentSteps: steps, content, sources });
        } else if (event === "mcp_call") {
          const p = JSON.parse(data) as McpAction;
          const known = actions.some((a) => a.id === p.id);
          actions = known
            ? actions.map((a) => (a.id === p.id ? { ...a, status: p.status, output: p.output } : a))
            : [...actions, p];
          if (p.status === "running") content = ""; // same as a search: what came before was narration
          patch({ actions, content });
        } else if (event === "approval_required") {
          const p = JSON.parse(data) as PendingApproval;
          setTurns((prev) =>
            prev.map((t) =>
              t.id === assistantId ? { ...t, approvals: [...(t.approvals ?? []).filter((a) => a.call_id !== p.call_id), p] } : t,
            ),
          );
        } else if (event === "token") {
          const payload = JSON.parse(data) as { delta: string };
          content += payload.delta;
          patch({ content });
        } else if (event === "done") {
          const payload = JSON.parse(data) as { finish_reason: string };
          // Paused for approval: the answer comes with the resume, so drop the narration.
          patch(payload.finish_reason === "approval_required" ? { isStreaming: false, content: "", sources } : { isStreaming: false, sources });
        } else if (event === "error") {
          const payload = JSON.parse(data) as { error: string };
          patch({ isStreaming: false, error: payload.error });
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") patch({ isStreaming: false, error: String(e) });
    }
  }

  /** Approve or reject a call the paused turn waits on, and stream the rest of the turn. */
  async function decideApproval(turn: ChatTurn, callId: number, approve: boolean, args?: Record<string, unknown>) {
    if (!agent || activeSessionId == null || streaming) return;
    setStreaming(true);
    const remaining = (turn.approvals ?? []).filter((a) => a.call_id !== callId);
    setTurns((prev) =>
      prev.map((t) => (t.id === turn.id ? { ...t, approvals: remaining, isStreaming: true, error: undefined } : t)),
    );
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await consumeStream(
        SessionsApi.decide(agent.id, activeSessionId, [{ call_id: callId, approve, args: approve ? args : null }], ctrl.signal),
        turn.id,
        turn,
      );
    } finally {
      setStreaming(false);
      abortRef.current = null;
      qc.invalidateQueries({ queryKey: ["sessions", agent.id] });
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (isSubmitEnter(e) && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function stopStream() {
    abortRef.current?.abort();
  }

  return (
    <>
      {/* Mobile backdrop for sidebar */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile backdrop for prompts panel */}
      {showPrompts && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => setShowPrompts(false)}
        />
      )}

    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Sessions sidebar */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 transition-transform duration-200",
          "md:static md:w-52 md:shrink-0 md:translate-x-0 md:z-auto",
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
      >
        <Card className="flex h-full flex-col overflow-hidden p-0 rounded-none md:rounded-2xl">
          <SessionSidebar
            sessions={sessions}
            activeId={activeSessionId}
            onSelect={(id) => {
              if (id !== activeSessionId) {
                stopStream();
                setActiveSessionId(id);
              }
              setSidebarOpen(false);
            }}
            onDelete={(id) => deleteSession.mutate(id)}
            onNew={() => createSession.mutate()}
            creating={createSession.isPending}
            disabled={!agent}
            onClose={() => setSidebarOpen(false)}
          />
        </Card>
      </div>

      {/* Chat area */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header */}
        <div className="mb-3 flex items-center justify-between gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <button
              className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700 md:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <MenuIcon />
            </button>
            {agent && (
              <span className="flex items-center gap-1.5 text-sm font-semibold text-[#2D3748] dark:text-gray-100">
                <span>{getAgentTheme(agent).icon}</span>
                {agents.length > 1 ? (
                  // Switch agents without leaving the chat; each keeps its own sessions.
                  <select
                    aria-label="Agent"
                    value={agent.id}
                    onChange={(e) => {
                      const next = agents.find((a) => a.id === Number(e.target.value));
                      if (next) selectAgent(next);
                    }}
                    className="rounded-lg border border-transparent bg-transparent py-0.5 pr-6 text-sm font-semibold hover:border-gray-200 focus:outline-none dark:hover:border-gray-600"
                  >
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  agent.name
                )}
              </span>
            )}
            {agent && <Badge tone="slate">{agent.model_label}</Badge>}
            {activePrompt ? (
              <Badge tone="green">{activePrompt.name}</Badge>
            ) : (
              <Badge tone="slate">Default prompt</Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant={showGraph ? "primary" : "secondary"}
              onClick={() => setShowGraph((p) => !p)}
              className="hidden items-center gap-1.5 lg:flex"
            >
              Graph
            </Button>
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
            {!agent ? (
              <div className="flex h-full items-center justify-center text-sm text-gray-400">
                Select an agent to start chatting.
              </div>
            ) : loadingMessages ? (
              <div className="flex h-full items-center justify-center">
                <span className="inline-flex gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-300 [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-300 [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-300" />
                </span>
              </div>
            ) : turns.length === 0 ? (
              <AgentWelcome agent={agent} onAsk={(q) => void sendMessage(q)} />
            ) : (
              (() => {
                // Answers streamed in this view have no index from the server yet;
                // number them the way the server does — finished answers only.
                let answers = 0;
                // User messages are counted the same way for edit/regenerate.
                let users = -1;
                let lastQuestion: { index: number; content: string } | null = null;
                const canRerun = !streaming && activeSessionId != null;
                return turns.map((turn, i) => {
                  const rateable = turn.role === "assistant" && !turn.isStreaming && !turn.error && !!turn.content;
                  const index = rateable ? (turn.turnIndex ?? answers) : undefined;
                  if (rateable) answers = index! + 1;
                  if (turn.role === "user") lastQuestion = { index: ++users, content: turn.content };
                  const question = lastQuestion;
                  const isLatestAnswer = turn.role === "assistant" && i === turns.length - 1;
                  return (
                    <MessageBubble
                      key={turn.id}
                      turn={turn}
                      onRate={index != null ? (r, c) => void rateTurn(turn.id, index, r, c) : undefined}
                      onEdit={
                        turn.role === "user" && canRerun
                          ? (text) => void sendMessage(text, { replaceTurn: question!.index })
                          : undefined
                      }
                      onRegenerate={
                        isLatestAnswer && canRerun && question && !turn.approvals?.length
                          ? () => void sendMessage(question.content, { replaceTurn: question.index, regenerate: true })
                          : undefined
                      }
                      busy={streaming}
                      onDecide={turn.approvals?.length ? (id, ok, args) => void decideApproval(turn, id, ok, args) : undefined}
                    />
                  );
                });
              })()
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-100 p-3 dark:border-gray-700">
            <div className="mb-2 flex items-center gap-1 text-[11px]">
              <span className="mr-1 text-gray-400 dark:text-gray-500">Retrieval</span>
              {(["auto", "on", "off"] as RetrievalMode[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setRetrievalMode(mode)}
                  className={cn(
                    "rounded border px-2 py-0.5 transition-colors capitalize",
                    retrievalMode === mode
                      ? "border-indigo-400 bg-indigo-50 text-indigo-700 dark:border-indigo-500 dark:bg-indigo-900/40 dark:text-indigo-300"
                      : "border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-500 dark:border-gray-600 dark:text-gray-500",
                  )}
                >
                  {mode}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <Textarea
                rows={2}
                className="resize-none text-sm"
                placeholder={
                  !agent
                    ? "Select an agent first"
                    : `Ask ${agent.name}… (Enter to send, Shift+Enter for newline)`
                }
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={!agent || streaming}
              />
              {streaming ? (
                <Button variant="danger" onClick={stopStream} className="self-end">
                  Stop
                </Button>
              ) : (
                <Button
                  onClick={() => void sendMessage()}
                  disabled={!agent || !input.trim()}
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

      {/* Execution graph panel — hidden on small screens, where width is scarce */}
      {showGraph && !showPrompts && (
        <div className="hidden lg:block lg:w-[360px] lg:shrink-0 xl:w-[440px] 2xl:w-[520px]">
          <Card className="flex h-full flex-col overflow-hidden rounded-2xl p-0">
            <RunInspector run={run} streaming={streaming} onHide={() => setShowGraph(false)} />
          </Card>
        </div>
      )}

      {/* System prompts panel */}
      {showPrompts && agent && (
        <div className="fixed inset-y-0 right-0 z-50 w-full max-w-sm md:static md:w-80 md:shrink-0 md:z-auto">
          <Card className="flex h-full flex-col overflow-hidden rounded-none md:rounded-2xl">
            <SystemPromptsPanel
              agentId={agent.id}
              onClose={() => setShowPrompts(false)}
              isAdmin={isAdmin}
            />
          </Card>
        </div>
      )}
    </div>
    </>
  );
}
