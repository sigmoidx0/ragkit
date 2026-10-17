import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { AgentsApi, WorkspacesApi } from "@/api/endpoints";
import type { AgentCard, WorkspaceWithRole } from "@/api/types";

const WORKSPACE_KEY = "ragkit.workspace_id";
// workspace id → last agent used there, so switching back restores it.
const AGENT_KEY = "ragkit.agent_by_workspace";

function readAgentMap(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(AGENT_KEY) ?? "{}");
  } catch {
    return {};
  }
}

interface WorkspaceContextValue {
  workspaces: WorkspaceWithRole[];
  /** The workspace whose documents, sets and members the UI shows. */
  workspace: WorkspaceWithRole | null;
  selectWorkspace: (workspace: WorkspaceWithRole) => void;
  /** Agents in the current workspace. */
  agents: AgentCard[];
  /** The agent Chat, Agent Settings and Evaluate work on. */
  agent: AgentCard | null;
  selectAgent: (agent: AgentCard) => void;
  isWorkspaceAdmin: boolean;
  loading: boolean;
  /** Reload workspaces and agents — after creating, renaming or reconfiguring. */
  refresh: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<WorkspaceWithRole[]>([]);
  const [workspaceId, setWorkspaceId] = useState<number | null>(() => {
    const saved = localStorage.getItem(WORKSPACE_KEY);
    return saved ? Number(saved) : null;
  });
  const [agents, setAgents] = useState<AgentCard[]>([]);
  const [agentId, setAgentId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const loadAgents = useCallback(async (wsId: number) => {
    const list = await AgentsApi.listMine(wsId);
    setAgents(list);
    const remembered = readAgentMap()[String(wsId)];
    setAgentId(list.find((a) => a.id === remembered)?.id ?? list[0]?.id ?? null);
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const list = await WorkspacesApi.listMine();
      setWorkspaces(list);
      const saved = Number(localStorage.getItem(WORKSPACE_KEY));
      const current = list.find((w) => w.id === saved) ?? list[0] ?? null;
      setWorkspaceId(current?.id ?? null);
      if (current) await loadAgents(current.id);
      else setAgents([]);
    } catch {
      setWorkspaces([]);
      setAgents([]);
    } finally {
      setLoading(false);
    }
  }, [loadAgents]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectWorkspace = useCallback(
    (w: WorkspaceWithRole) => {
      localStorage.setItem(WORKSPACE_KEY, String(w.id));
      setWorkspaceId(w.id);
      void loadAgents(w.id);
    },
    [loadAgents],
  );

  const selectAgent = useCallback((a: AgentCard) => {
    const map = readAgentMap();
    map[String(a.workspace_id)] = a.id;
    localStorage.setItem(AGENT_KEY, JSON.stringify(map));
    setAgentId(a.id);
  }, []);

  const value = useMemo(() => {
    const workspace = workspaces.find((w) => w.id === workspaceId) ?? null;
    return {
      workspaces,
      workspace,
      selectWorkspace,
      agents,
      agent: agents.find((a) => a.id === agentId) ?? null,
      selectAgent,
      isWorkspaceAdmin: workspace?.role === "admin",
      loading,
      refresh,
    };
  }, [workspaces, workspaceId, selectWorkspace, agents, agentId, selectAgent, loading, refresh]);

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}
