import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { DocumentSetsApi, DocumentsApi } from "@/api/endpoints";
import type { DocumentSet } from "@/api/types";
import { Badge, Button, Card, Input, Label, Textarea } from "@/components/ui";
import { cn } from "@/lib/cn";
import { useWorkspace } from "@/workspace/WorkspaceProvider";

interface Draft {
  name: string;
  description: string;
  documentIds: number[];
}

const EMPTY_DRAFT: Draft = { name: "", description: "", documentIds: [] };

/**
 * Document sets: named groups of the workspace's documents. A document can be
 * in any number of sets; each agent picks the sets it searches (in Agent
 * Settings) and searches only those — an agent with none searches nothing.
 */
export default function DocumentSetsPage() {
  const { workspace, refresh } = useWorkspace();
  const qc = useQueryClient();
  const wsId = workspace?.id;
  const canEdit = workspace?.role !== "viewer";

  const { data: sets = [] } = useQuery({
    queryKey: ["document-sets", wsId],
    queryFn: () => DocumentSetsApi.list(wsId!),
    enabled: wsId != null,
  });
  const { data: docs } = useQuery({
    queryKey: ["documents-all", wsId],
    // The API caps a page at 200 — enough to pick from in a workspace.
    queryFn: () => DocumentsApi.list(wsId!, { limit: 200 }),
    enabled: wsId != null,
  });
  const documents = docs?.items ?? [];

  // null = nothing selected; "new" = creating; a number = editing that set.
  const [selected, setSelected] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [filter, setFilter] = useState("");
  const current = typeof selected === "number" ? sets.find((s) => s.id === selected) ?? null : null;

  useEffect(() => {
    if (current) {
      setDraft({ name: current.name, description: current.description ?? "", documentIds: current.document_ids });
    } else if (selected === "new") {
      setDraft(EMPTY_DRAFT);
    }
  }, [current, selected]);

  // Pick the first set when the page opens, so the editor isn't empty.
  useEffect(() => {
    if (selected == null && sets.length) setSelected(sets[0].id);
  }, [sets, selected]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["document-sets", wsId] });
    void refresh(); // agent cards show how many documents each can search
  };

  const save = useMutation({
    mutationFn: () => {
      const body = { name: draft.name.trim(), description: draft.description.trim() || null, document_ids: draft.documentIds };
      return selected === "new" ? DocumentSetsApi.create(wsId!, body) : DocumentSetsApi.update(wsId!, selected as number, body);
    },
    onSuccess: (saved) => {
      toast.success(selected === "new" ? "Document set created" : "Document set saved");
      setSelected(saved.id);
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to save"),
  });

  const remove = useMutation({
    mutationFn: (id: number) => DocumentSetsApi.remove(wsId!, id),
    onSuccess: () => {
      toast.success("Document set deleted");
      setSelected(null);
      invalidate();
    },
    // In use by an agent: the server explains which one.
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to delete"),
  });

  const dirty = useMemo(() => {
    if (selected === "new") return draft.name.trim().length > 0;
    if (!current) return false;
    return (
      draft.name !== current.name ||
      draft.description !== (current.description ?? "") ||
      [...draft.documentIds].sort().join() !== [...current.document_ids].sort().join()
    );
  }, [draft, current, selected]);

  if (!workspace) return <Card className="p-8 text-sm text-gray-500">Select a workspace first.</Card>;

  const shownDocs = documents.filter((d) => d.title.toLowerCase().includes(filter.toLowerCase()));
  const toggleDoc = (id: number) =>
    setDraft((d) => ({
      ...d,
      documentIds: d.documentIds.includes(id) ? d.documentIds.filter((x) => x !== id) : [...d.documentIds, id],
    }));

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[#2D3748] dark:text-gray-100">Document sets · {workspace.name}</h1>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Group documents so each agent searches only what it should. A document can be in several sets; an agent
            searches only the sets selected in its settings.
          </p>
        </div>
        {canEdit && <Button onClick={() => setSelected("new")}>+ New set</Button>}
      </div>

      <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* Sets */}
        <Card className="h-fit p-2">
          {sets.length === 0 && selected !== "new" ? (
            <p className="p-4 text-center text-xs text-gray-400">No sets yet.</p>
          ) : (
            sets.map((s: DocumentSet) => (
              <button
                key={s.id}
                onClick={() => setSelected(s.id)}
                className={cn(
                  "w-full rounded-xl px-3 py-2.5 text-left transition-colors",
                  selected === s.id ? "bg-teal-50 dark:bg-teal-900/30" : "hover:bg-gray-50 dark:hover:bg-gray-700/40",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-gray-800 dark:text-gray-100">{s.name}</span>
                  <span className="shrink-0 font-mono text-[11px] text-gray-400">{s.document_ids.length} docs</span>
                </div>
                <p className="mt-0.5 truncate text-[11px] text-gray-400">
                  {s.used_by.length ? `used by ${s.used_by.map((a) => a.name).join(", ")}` : "not used by any agent"}
                </p>
              </button>
            ))
          )}
        </Card>

        {/* Editor */}
        {selected == null ? (
          <Card className="p-10 text-center text-sm text-gray-500 dark:text-gray-400">
            {canEdit ? "Create a set to start grouping documents." : "No document sets in this workspace yet."}
          </Card>
        ) : (
          <Card className="space-y-4 p-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="set-name">Name</Label>
                <Input
                  id="set-name"
                  value={draft.name}
                  disabled={!canEdit}
                  placeholder="e.g. HR policies"
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
              </div>
              <div>
                <Label>Used by</Label>
                <div className="flex min-h-[38px] flex-wrap items-center gap-1">
                  {current?.used_by.length ? (
                    current.used_by.map((a) => (
                      <Badge key={a.id} tone="green">
                        {a.name}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-xs text-gray-400">
                      No agent yet — select this set in an agent's settings.
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div>
              <Label htmlFor="set-description">Description</Label>
              <Textarea
                id="set-description"
                rows={2}
                value={draft.description}
                disabled={!canEdit}
                placeholder="What belongs in this set?"
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              />
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between gap-2">
                <Label>
                  Documents ({draft.documentIds.length} of {documents.length})
                </Label>
                <Input className="w-56" value={filter} placeholder="Filter by title" onChange={(e) => setFilter(e.target.value)} />
              </div>
              <div className="max-h-96 divide-y overflow-y-auto rounded-xl border dark:divide-gray-700 dark:border-gray-700">
                {shownDocs.length === 0 ? (
                  <p className="p-4 text-center text-xs text-gray-400">
                    {documents.length ? "No documents match." : "Upload documents first."}
                  </p>
                ) : (
                  shownDocs.map((d) => (
                    <label
                      key={d.id}
                      className="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700/40"
                    >
                      <input
                        type="checkbox"
                        className="accent-teal-500"
                        disabled={!canEdit}
                        checked={draft.documentIds.includes(d.id)}
                        onChange={() => toggleDoc(d.id)}
                      />
                      <span className="min-w-0 flex-1 truncate text-gray-700 dark:text-gray-200">{d.title}</span>
                      <span className="shrink-0 text-[11px] text-gray-400">{d.source_filename}</span>
                    </label>
                  ))
                )}
              </div>
            </div>

            {canEdit && (
              <div className="flex items-center justify-between border-t pt-4 dark:border-gray-700">
                {current ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(current.id)}
                    title={current.used_by.length ? "Remove it from the agents using it first" : undefined}
                  >
                    Delete set
                  </Button>
                ) : (
                  <span />
                )}
                <div className="flex gap-2">
                  {selected === "new" && (
                    <Button variant="secondary" size="sm" onClick={() => setSelected(sets[0]?.id ?? null)}>
                      Cancel
                    </Button>
                  )}
                  <Button size="sm" disabled={!dirty || !draft.name.trim() || save.isPending} onClick={() => save.mutate()}>
                    {save.isPending ? "Saving…" : selected === "new" ? "Create set" : "Save"}
                  </Button>
                </div>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
