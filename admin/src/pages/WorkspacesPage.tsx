import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { WorkspacesApi } from "@/api/endpoints";
import { Button, Card, FormField, Input, SectionHeading } from "@/components/ui";
import { DataTable, type Column } from "@/components/DataTable";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useWorkspace } from "@/workspace/WorkspaceProvider";
import type { Workspace } from "@/api/types";

export default function WorkspacesPage() {
  const qc = useQueryClient();
  const { refresh: refreshWorkspaces } = useWorkspace();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<Workspace | null>(null);

  const listQuery = useQuery({
    queryKey: ["workspaces-all"],
    queryFn: () => WorkspacesApi.listAll(),
  });

  const createMutation = useMutation({
    mutationFn: () => WorkspacesApi.create(name, slug),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["workspaces-all"] });
      await refreshWorkspaces();
      setName("");
      setSlug("");
      toast.success("Workspace created");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to create workspace"),
  });

  const deleteMutation = useMutation({
    mutationFn: (workspaceId: number) => WorkspacesApi.remove(workspaceId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["workspaces-all"] });
      await refreshWorkspaces();
      toast.success("Workspace deleted");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to delete workspace"),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !slug.trim()) return;
    createMutation.mutate();
  };

  const workspaces = listQuery.data ?? [];

  const SERVICE_COLUMNS: Column<Workspace>[] = [
    { header: "Name", render: (s) => <span className="font-medium text-[#2D3748] dark:text-gray-100">{s.name}</span> },
    { header: "Slug", render: (s) => <span className="font-mono text-[#A0AEC0]">{s.slug}</span> },
    {
      header: "Created",
      render: (s) => <span className="text-[#A0AEC0]">{new Date(s.created_at).toLocaleString()}</span>,
    },
    {
      header: "",
      className: "text-right",
      render: (s) => (
        <Button
          variant="danger"
          size="sm"
          disabled={deleteMutation.isPending}
          onClick={() => setConfirmDelete(s)}
        >
          Delete
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <ConfirmDialog
        open={confirmDelete != null}
        title="Delete workspace?"
        confirmLabel="Delete"
        onConfirm={() => {
          if (confirmDelete) deleteMutation.mutate(confirmDelete.id);
          setConfirmDelete(null);
        }}
        onCancel={() => setConfirmDelete(null)}
      >
        Delete <strong>{confirmDelete?.name}</strong> with its agents, documents and chats? This cannot be undone.
      </ConfirmDialog>
      <Card className="p-5">
        <SectionHeading className="mb-3">New Workspace</SectionHeading>
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2">
          <FormField label="Name" htmlFor="svc-name">
            <Input
              id="svc-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Workspace"
              required
            />
          </FormField>
          <FormField label="Slug" htmlFor="svc-slug">
            <Input
              id="svc-slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="my-workspace"
              required
            />
          </FormField>
          <div className="md:col-span-2">
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating…" : "Create"}
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <DataTable<Workspace>
          columns={SERVICE_COLUMNS}
          rows={workspaces}
          rowKey={(s) => s.id}
          isLoading={listQuery.isLoading}
          emptyMessage="No workspaces yet."
        />
      </Card>
    </div>
  );
}
