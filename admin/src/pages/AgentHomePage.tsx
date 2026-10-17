import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { AgentsApi } from "@/api/endpoints";

import type { AgentCard, AgentSummary } from "@/api/types";
import { useAuth } from "@/auth/AuthProvider";
import { Badge, Button, Card, Input, Label, Select } from "@/components/ui";
import { getAgentTheme } from "@/lib/agentTheme";
import { isSubmitEnter } from "@/lib/keys";
import { useWorkspace } from "@/workspace/WorkspaceProvider";

/** Where a starter question travels to ChatPage, which sends it on arrival. */
export interface ChatLaunchState {
  prompt?: string;
}

const MAX_CHIPS = 3;

function AgentTile({
  agent,
  onOpen,
  onAsk,
  onConfigure,
}: {
  agent: AgentCard;
  onOpen: () => void;
  onAsk: (prompt: string) => void;
  onConfigure?: () => void;
}) {
  const theme = getAgentTheme(agent);
  const cfg = agent.agent_config;
  const enabledRoutes = Object.entries(cfg.routes).filter(([, r]) => r.enabled).map(([name]) => name);
  const misconfigured = agent.model_label === "misconfigured";

  return (
    <Card className="group flex flex-col overflow-hidden transition-shadow hover:shadow-lg">
      {/* Banner: the whole tile opens the chat, chips ask a question directly */}
      <button
        onClick={onOpen}
        className="flex items-center gap-3 px-5 py-4 text-left text-white"
        style={{ background: `linear-gradient(135deg, ${theme.gradientFrom}, ${theme.gradientTo})` }}
      >
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/20 text-2xl backdrop-blur">
          {theme.icon}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-base font-bold">{agent.name}</span>
          <span className="block text-[11px] capitalize opacity-80">{agent.role}</span>
        </span>
        <span className="text-lg opacity-0 transition-opacity group-hover:opacity-100">→</span>
      </button>

      <div className="flex flex-1 flex-col gap-3 p-5">
        <p className="min-h-[2.5rem] text-sm text-gray-600 dark:text-gray-300">
          {cfg.description || (
            <span className="text-gray-400 dark:text-gray-500">No description yet.</span>
          )}
        </p>

        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={misconfigured ? "red" : "slate"}>{agent.model_label}</Badge>
          <Badge tone={agent.document_count ? "blue" : "amber"}>
            {agent.document_count} doc{agent.document_count === 1 ? "" : "s"}
          </Badge>
          <Badge tone="green">{enabledRoutes.length} routes</Badge>
          {cfg.pipeline_id != null && <Badge tone="amber">custom pipeline</Badge>}
          {(cfg.mcp_tools?.length ?? 0) > 0 && (
            <Badge tone="slate">
              {cfg.mcp_tools.length} MCP tool{cfg.mcp_tools.length === 1 ? "" : "s"}
            </Badge>
          )}
        </div>

        {cfg.starter_questions.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {cfg.starter_questions.slice(0, MAX_CHIPS).map((q) => (
              <button
                key={q}
                onClick={() => onAsk(q)}
                className="truncate rounded-xl border border-gray-200 px-3 py-1.5 text-left text-xs text-gray-600 transition-colors hover:border-gray-300 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                title={q}
              >
                💬 {q}
              </button>
            ))}
          </div>
        )}

        <div className="mt-auto flex items-center justify-between pt-2">
          <button
            onClick={onOpen}
            className="rounded-xl px-3 py-1.5 text-xs font-semibold text-white shadow-sm"
            style={{ background: theme.accent }}
          >
            Start chat
          </button>
          {onConfigure && (
            <button
              onClick={onConfigure}
              className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            >
              Configure
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}

/** Admins create agents here; a new agent can start from another's settings. */
function NewAgentTile({ agents, onCreated }: { agents: AgentCard[]; onCreated: (agent: AgentSummary) => void }) {
  const { workspace } = useWorkspace();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [copyFrom, setCopyFrom] = useState<number | "">("");

  const create = useMutation({
    mutationFn: () => AgentsApi.create(workspace!.id, name.trim(), copyFrom === "" ? null : copyFrom),
    onSuccess: (agent) => {
      toast.success(`Agent "${agent.name}" created`);
      setOpen(false);
      setName("");
      setCopyFrom("");
      onCreated(agent);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to create agent"),
  });

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex min-h-[18rem] flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-gray-200 text-gray-400 transition-colors hover:border-teal-300 hover:text-teal-600 dark:border-gray-700"
      >
        <span className="text-3xl">+</span>
        <span className="text-sm font-semibold">New agent</span>
        <span className="px-6 text-center text-xs">
          Another assistant over this workspace's documents, with its own model, router and document sets.
        </span>
      </button>
    );
  }

  return (
    <Card className="flex min-h-[18rem] flex-col gap-3 p-5">
      <p className="text-sm font-bold text-[#2D3748] dark:text-gray-100">New agent in {workspace?.name}</p>
      <div>
        <Label htmlFor="new-agent-name">Name</Label>
        <Input
          id="new-agent-name"
          autoFocus
          value={name}
          placeholder="e.g. HR assistant"
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => isSubmitEnter(e) && name.trim() && create.mutate()}
        />
      </div>
      <div>
        <Label htmlFor="new-agent-copy">Start from</Label>
        <Select
          id="new-agent-copy"
          value={copyFrom}
          onChange={(e) => setCopyFrom(e.target.value ? Number(e.target.value) : "")}
        >
          <option value="">Default settings</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              Copy of {a.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="mt-auto flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={() => setOpen(false)}>
          Cancel
        </Button>
        <Button size="sm" disabled={!name.trim() || create.isPending} onClick={() => create.mutate()}>
          {create.isPending ? "Creating…" : "Create"}
        </Button>
      </div>
    </Card>
  );
}

/**
 * One box for a question when the user doesn't know which agent to ask. The
 * server picks the agent (it routes, it doesn't answer); the question then opens
 * in that agent's chat, exactly as a starter question would.
 */
function AskAnything({
  workspaceId,
  agents,
  onRouted,
}: {
  workspaceId: number;
  agents: AgentCard[];
  onRouted: (agent: AgentCard, question: string) => void;
}) {
  const [question, setQuestion] = useState("");
  const route = useMutation({
    mutationFn: (q: string) => AgentsApi.route(workspaceId, q),
    onSuccess: (result, q) => {
      const agent = agents.find((a) => a.id === result.agent_id);
      if (!agent) {
        toast.error("Couldn't open the chosen agent — pick one below.");
        return;
      }
      toast.success(`Asking ${agent.name}`, { description: result.reason || undefined });
      onRouted(agent, q);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't choose an agent — pick one below."),
  });
  const submit = () => question.trim() && !route.isPending && route.mutate(question.trim());

  return (
    <Card className="mb-6 p-4">
      <Label>Not sure which agent to ask?</Label>
      <div className="mt-1.5 flex gap-2">
        <Input
          value={question}
          placeholder="Ask anything — the right agent will pick it up"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => isSubmitEnter(e) && submit()}
          disabled={route.isPending}
        />
        <Button disabled={!question.trim() || route.isPending} onClick={submit}>
          {route.isPending ? "Choosing…" : "Ask"}
        </Button>
      </div>
    </Card>
  );
}

export default function AgentHomePage() {
  const { workspace, agents, loading, selectAgent, isWorkspaceAdmin, refresh } = useWorkspace();
  const { user } = useAuth();
  const navigate = useNavigate();

  const open = (agent: AgentCard, state?: ChatLaunchState) => {
    selectAgent(agent);
    navigate("/chat", { state });
  };

  const greetingName = user?.email.split("@")[0];

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#2D3748] dark:text-gray-100">
          {greetingName ? `Hi, ${greetingName}` : "Welcome"}
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          {workspace
            ? `Agents in ${workspace.name}. Each shares the workspace's documents but has its own model, router and document sets.`
            : "Pick a workspace to see its agents."}
        </p>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-72 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800" />
          ))}
        </div>
      ) : !workspace ? (
        <Card className="p-10 text-center text-sm text-gray-500 dark:text-gray-400">
          You don't belong to any workspace yet. Ask an administrator to add you to one.
        </Card>
      ) : (
        <>
        {agents.length > 1 && (
          <AskAnything workspaceId={workspace.id} agents={agents} onRouted={(agent, prompt) => open(agent, { prompt })} />
        )}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <AgentTile
              key={agent.id}
              agent={agent}
              onOpen={() => open(agent)}
              onAsk={(prompt) => open(agent, { prompt })}
              onConfigure={
                isWorkspaceAdmin
                  ? () => {
                      selectAgent(agent);
                      navigate("/agent-settings");
                    }
                  : undefined
              }
            />
          ))}
          {isWorkspaceAdmin && (
            <NewAgentTile
              agents={agents}
              onCreated={async (created) => {
                await refresh();
                // Straight to its settings — a new agent is mostly configuration.
                const card = (await AgentsApi.listMine(created.workspace_id)).find((a) => a.id === created.id);
                if (card) selectAgent(card);
                navigate("/agent-settings");
              }}
            />
          )}
          {agents.length === 0 && !isWorkspaceAdmin && (
            <Card className="p-10 text-center text-sm text-gray-500 dark:text-gray-400 sm:col-span-2 lg:col-span-3">
              This workspace has no agents yet.
            </Card>
          )}
        </div>
        </>
      )}
    </div>
  );
}
