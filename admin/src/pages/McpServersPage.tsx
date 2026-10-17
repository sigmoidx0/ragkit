import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { McpApi } from "@/api/endpoints";
import type { McpCallStatus, McpServer, McpServerInput, McpToolCall } from "@/api/types";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge, Button, Card, FormField, Input, Textarea } from "@/components/ui";
import { cn } from "@/lib/cn";
import { useWorkspace } from "@/workspace/WorkspaceProvider";

const ENV_PREFIX = "MCP_TOKEN_";

interface Draft {
  name: string;
  url: string;
  auth_env_var: string;
  description: string;
}

const EMPTY: Draft = { name: "", url: "", auth_env_var: "", description: "" };

/**
 * The workspace's MCP servers: register a remote server, see the tools it
 * offers, and review what agents did with them. Which agent may use which tool
 * — and whether a call needs approval — is set per agent in Agent Settings.
 */
export default function McpServersPage() {
  const { workspace } = useWorkspace();
  const wsId = workspace?.id;
  const qc = useQueryClient();
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [confirmDelete, setConfirmDelete] = useState<McpServer | null>(null);

  const { data: servers = [], isLoading } = useQuery({
    queryKey: ["mcp-servers", wsId],
    queryFn: () => McpApi.list(wsId!),
    enabled: wsId != null,
  });
  const { data: calls = [] } = useQuery({
    queryKey: ["mcp-calls", wsId],
    queryFn: () => McpApi.calls(wsId!, 30),
    enabled: wsId != null,
    refetchInterval: 10_000,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["mcp-servers", wsId] });
  const onError = (e: unknown) => toast.error(e instanceof Error ? e.message : "Request failed");

  const save = useMutation({
    mutationFn: () => {
      const body: McpServerInput = {
        name: draft.name.trim(),
        url: draft.url.trim(),
        auth_env_var: draft.auth_env_var.trim() || null,
        description: draft.description.trim() || null,
      };
      return editing === "new" ? McpApi.create(wsId!, body) : McpApi.update(wsId!, editing as number, body);
    },
    onSuccess: (server) => {
      if (server.last_error) toast.warning(`Saved, but connecting failed: ${server.last_error}`);
      else toast.success(`${server.name}: ${server.tools.length} tools found`);
      setEditing(null);
      invalidate();
    },
    onError,
  });
  const refresh = useMutation({
    mutationFn: (id: number) => McpApi.refresh(wsId!, id),
    onSuccess: (server) => {
      if (server.last_error) toast.error(server.last_error);
      else toast.success(`${server.name}: ${server.tools.length} tools`);
      invalidate();
    },
    onError,
  });
  const toggle = useMutation({
    mutationFn: (s: McpServer) => McpApi.update(wsId!, s.id, { enabled: !s.enabled }),
    onSuccess: invalidate,
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: number) => McpApi.remove(wsId!, id),
    onSuccess: () => {
      toast.success("Server removed");
      invalidate();
    },
    onError,
  });

  if (!workspace) return <Card className="p-8 text-sm text-gray-500">Select a workspace first.</Card>;

  const startEdit = (s: McpServer | null) => {
    setEditing(s ? s.id : "new");
    setDraft(
      s ? { name: s.name, url: s.url, auth_env_var: s.auth_env_var ?? "", description: s.description ?? "" } : EMPTY,
    );
  };
  const envInvalid = draft.auth_env_var.trim() !== "" && !/^MCP_TOKEN_[A-Z0-9_]+$/.test(draft.auth_env_var.trim());

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <ConfirmDialog
        open={confirmDelete != null}
        title="Remove MCP server?"
        confirmLabel="Remove"
        onConfirm={() => {
          if (confirmDelete) remove.mutate(confirmDelete.id);
          setConfirmDelete(null);
        }}
        onCancel={() => setConfirmDelete(null)}
      >
        Remove <strong>{confirmDelete?.name}</strong>? Agents using its tools must drop them first.
      </ConfirmDialog>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[#2D3748] dark:text-gray-100">MCP servers · {workspace.name}</h1>
          <p className="max-w-3xl text-xs text-gray-500 dark:text-gray-400">
            Remote MCP servers this workspace's agents can call. Choose tools per agent in Agent Settings — lookups
            can run on their own; anything that changes data can wait for the user's approval in the chat.
          </p>
        </div>
        {editing == null && <Button onClick={() => startEdit(null)}>+ Add server</Button>}
      </div>

      {editing != null && (
        <Card className="p-5">
          <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2">
            <FormField label="Name" htmlFor="mcp-name">
              <Input
                id="mcp-name"
                required
                value={draft.name}
                placeholder="e.g. 정비 데스크"
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </FormField>
            <FormField label="URL (streamable HTTP)" htmlFor="mcp-url">
              <Input
                id="mcp-url"
                required
                value={draft.url}
                placeholder="https://mcp.example.com/mcp"
                onChange={(e) => setDraft({ ...draft, url: e.target.value })}
              />
            </FormField>
            <div>
              <FormField label="Token variable (optional)" htmlFor="mcp-env">
                <Input
                  id="mcp-env"
                  value={draft.auth_env_var}
                  placeholder={`${ENV_PREFIX}CRM`}
                  className="font-mono"
                  onChange={(e) => setDraft({ ...draft, auth_env_var: e.target.value.toUpperCase() })}
                />
              </FormField>
              <p className={cn("mt-1 text-[11px]", envInvalid ? "text-red-500" : "text-gray-400")}>
                Name of an environment variable on the ragkit server holding the bearer token. Only names starting
                with {ENV_PREFIX} are allowed, so other secrets can't be sent to an MCP server. The token itself is
                never stored here.
              </p>
            </div>
            <FormField label="Description (optional)" htmlFor="mcp-desc">
              <Textarea
                id="mcp-desc"
                rows={3}
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              />
            </FormField>
            <div className="flex justify-end gap-2 md:col-span-2">
              <Button type="button" variant="secondary" onClick={() => setEditing(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={save.isPending || envInvalid}>
                {save.isPending ? "Connecting…" : editing === "new" ? "Add and connect" : "Save"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {isLoading ? null : servers.length === 0 && editing == null ? (
        <Card className="p-10 text-center text-sm text-gray-500 dark:text-gray-400">
          No MCP servers yet. Add one to give this workspace's agents tools beyond document search.
        </Card>
      ) : (
        servers.map((s) => (
          <ServerCard
            key={s.id}
            server={s}
            busy={refresh.isPending || toggle.isPending}
            onRefresh={() => refresh.mutate(s.id)}
            onToggle={() => toggle.mutate(s)}
            onEdit={() => startEdit(s)}
            onDelete={() => setConfirmDelete(s)}
          />
        ))
      )}

      <RecentCalls calls={calls} />
    </div>
  );
}

function ServerCard({
  server: s,
  busy,
  onRefresh,
  onToggle,
  onEdit,
  onDelete,
}: {
  server: McpServer;
  busy: boolean;
  onRefresh: () => void;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <Card className={cn("p-5", !s.enabled && "opacity-70")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-bold text-[#2D3748] dark:text-gray-100">{s.name}</h2>
            {!s.enabled ? (
              <Badge tone="slate">disabled</Badge>
            ) : s.last_error ? (
              <Badge tone="red">connection failed</Badge>
            ) : (
              <Badge tone="green">{s.tools.length} tools</Badge>
            )}
            {s.auth_env_var && (
              <Badge tone={s.auth_configured ? "blue" : "amber"}>
                <span className="font-mono">{s.auth_env_var}</span>&nbsp;{s.auth_configured ? "set" : "not set"}
              </Badge>
            )}
          </div>
          <p className="mt-0.5 break-all font-mono text-[11px] text-gray-400">{s.url}</p>
          {s.description && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{s.description}</p>}
          {s.last_error && <p className="mt-1 text-xs text-red-500">{s.last_error}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" disabled={busy} onClick={onRefresh}>
            Refresh tools
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={onToggle}>
            {s.enabled ? "Disable" : "Enable"}
          </Button>
          <Button size="sm" variant="secondary" onClick={onEdit}>
            Edit
          </Button>
          <Button size="sm" variant="secondary" onClick={onDelete}>
            Remove
          </Button>
        </div>
      </div>

      {s.tools.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-xl border dark:border-gray-700">
          <table className="w-full min-w-[560px] text-left text-xs">
            <thead className="bg-gray-50 text-[11px] uppercase tracking-wide text-gray-400 dark:bg-gray-800">
              <tr>
                <th className="px-3 py-2">Tool</th>
                <th className="px-3 py-2">What it does</th>
                <th className="px-3 py-2">Kind</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {s.tools.map((t) => (
                <tr key={t.name}>
                  <td className="px-3 py-2 align-top">
                    <span className="block font-semibold text-gray-700 dark:text-gray-200">{t.title || t.name}</span>
                    <span className="font-mono text-[11px] text-gray-400">{t.name}</span>
                  </td>
                  <td className="px-3 py-2 align-top text-gray-500 dark:text-gray-400">
                    {t.description.split("\n")[0]}
                  </td>
                  <td className="px-3 py-2 align-top">
                    {t.read_only ? (
                      <Badge tone="green">read-only</Badge>
                    ) : t.destructive ? (
                      <Badge tone="red">destructive</Badge>
                    ) : (
                      <Badge tone="amber">writes</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-2 text-[11px] text-gray-400">
        {s.used_by.length ? `Used by ${s.used_by.map((a) => a.name).join(", ")}` : "No agent uses this server yet."}
        {s.tools_refreshed_at && ` · tools refreshed ${new Date(s.tools_refreshed_at).toLocaleString()}`}
      </p>
    </Card>
  );
}

const STATUS_TONE: Record<McpCallStatus, "green" | "red" | "amber" | "blue" | "slate"> = {
  auto: "slate",
  pending: "amber",
  approved: "green",
  rejected: "red",
  expired: "slate",
};

function RecentCalls({ calls }: { calls: McpToolCall[] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <Card className="p-5">
      <h2 className="text-sm font-bold text-[#2D3748] dark:text-gray-100">Recent tool calls</h2>
      <p className="mb-3 text-xs text-gray-500 dark:text-gray-400">
        Every MCP call by this workspace's agents: what ran on its own, what was approved or rejected, and by whom.
      </p>
      {calls.length === 0 ? (
        <p className="py-6 text-center text-xs text-gray-400">No calls yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead className="text-[11px] uppercase tracking-wide text-gray-400">
              <tr>
                <th className="py-2 pr-3">When</th>
                <th className="py-2 pr-3">Agent</th>
                <th className="py-2 pr-3">Tool</th>
                <th className="py-2 pr-3">Arguments</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2">Decided by</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {calls.map((c) => (
                <tr
                  key={c.id}
                  className="cursor-pointer align-top hover:bg-gray-50 dark:hover:bg-gray-700/30"
                  onClick={() => setOpen(open === c.id ? null : c.id)}
                >
                  <td className="whitespace-nowrap py-2 pr-3 tabular-nums text-gray-400">
                    {new Date(c.created_at).toLocaleString()}
                  </td>
                  <td className="py-2 pr-3 text-gray-700 dark:text-gray-200">{c.agent_name}</td>
                  <td className="py-2 pr-3">
                    <span className="font-mono text-gray-700 dark:text-gray-200">{c.tool}</span>
                    <span className="block text-[11px] text-gray-400">{c.server_name}</span>
                  </td>
                  <td className="max-w-xs py-2 pr-3 font-mono text-[11px] text-gray-500">
                    <span className={open === c.id ? "whitespace-pre-wrap break-words" : "line-clamp-2 break-words"}>
                      {JSON.stringify(c.approved_args ?? c.args)}
                    </span>
                    {c.approved_args && <span className="block font-sans text-violet-500">edited before approval</span>}
                    {open === c.id && c.result && (
                      <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-2 dark:bg-gray-900">
                        {c.result}
                      </pre>
                    )}
                  </td>
                  <td className="py-2 pr-3">
                    <Badge tone={c.is_error ? "red" : STATUS_TONE[c.status]}>{c.is_error ? `${c.status} · error` : c.status}</Badge>
                  </td>
                  <td className="py-2 text-gray-500">{c.decided_by ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
