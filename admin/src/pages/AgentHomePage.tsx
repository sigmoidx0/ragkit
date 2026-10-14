import { useNavigate } from "react-router-dom";

import type { AgentCard } from "@/api/types";
import { useAuth } from "@/auth/AuthProvider";
import { Badge, Card } from "@/components/ui";
import { getAgentTheme } from "@/lib/agentTheme";
import { useService } from "@/services/ServiceProvider";

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
          <Badge tone="blue">
            {agent.document_count} doc{agent.document_count === 1 ? "" : "s"}
          </Badge>
          <Badge tone="green">{enabledRoutes.length} routes</Badge>
          {cfg.pipeline_id != null && <Badge tone="amber">custom pipeline</Badge>}
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

export default function AgentHomePage() {
  const { services: agents, loading, select } = useService();
  const { user } = useAuth();
  const navigate = useNavigate();

  const open = (agent: AgentCard, state?: ChatLaunchState) => {
    select(agent);
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
          Pick an agent to chat with. Each one answers from its own documents, model, and router.
        </p>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-72 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800" />
          ))}
        </div>
      ) : agents.length === 0 ? (
        <Card className="p-10 text-center text-sm text-gray-500 dark:text-gray-400">
          You don't have access to any agents yet. Ask an administrator to add you to one.
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <AgentTile
              key={agent.id}
              agent={agent}
              onOpen={() => open(agent)}
              onAsk={(prompt) => open(agent, { prompt })}
              onConfigure={
                agent.role === "admin"
                  ? () => {
                      select(agent);
                      navigate("/agent-settings");
                    }
                  : undefined
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
