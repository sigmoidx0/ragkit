import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ServicesApi } from "@/api/endpoints";
import { Button, Card, Input, Label } from "@/components/ui";
import { DataTable, type Column } from "@/components/DataTable";
import { useService } from "@/services/ServiceProvider";
import type { Service } from "@/api/types";

export default function ServicesPage() {
  const qc = useQueryClient();
  const { refresh: refreshServiceContext } = useService();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  const listQuery = useQuery({
    queryKey: ["services-all"],
    queryFn: () => ServicesApi.listAll(),
  });

  const createMutation = useMutation({
    mutationFn: () => ServicesApi.create(name, slug),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["services-all"] });
      await refreshServiceContext();
      setName("");
      setSlug("");
      toast.success("Service created");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to create service"),
  });

  const deleteMutation = useMutation({
    mutationFn: (serviceId: number) => ServicesApi.remove(serviceId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["services-all"] });
      await refreshServiceContext();
      toast.success("Service deleted");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to delete service"),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !slug.trim()) return;
    createMutation.mutate();
  };

  const services = listQuery.data ?? [];

  const SERVICE_COLUMNS: Column<Service>[] = [
    { header: "Name", render: (s) => <span className="font-medium text-[#2D3748]">{s.name}</span> },
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
          onClick={() => {
            if (confirm(`Delete "${s.name}"? This cannot be undone.`)) {
              deleteMutation.mutate(s.id);
            }
          }}
        >
          Delete
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#A0AEC0]">
          New Service
        </h2>
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="svc-name">Name</Label>
            <Input
              id="svc-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Service"
              required
            />
          </div>
          <div>
            <Label htmlFor="svc-slug">Slug</Label>
            <Input
              id="svc-slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="my-service"
              required
            />
          </div>
          <div className="md:col-span-2">
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating…" : "Create"}
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <DataTable<Service>
          columns={SERVICE_COLUMNS}
          rows={services}
          rowKey={(s) => s.id}
          isLoading={listQuery.isLoading}
          emptyMessage="No services yet."
        />
      </Card>
    </div>
  );
}
