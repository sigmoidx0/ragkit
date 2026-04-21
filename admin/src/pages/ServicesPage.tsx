import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ServicesApi } from "@/api/endpoints";
import { Button, Card, Input, Label } from "@/components/ui";
import { useService } from "@/services/ServiceProvider";

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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Services</h1>

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">
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
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Slug</th>
              <th className="px-4 py-2">Created</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {listQuery.isLoading && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                  Loading…
                </td>
              </tr>
            )}
            {!listQuery.isLoading && services.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                  No services yet.
                </td>
              </tr>
            )}
            {services.map((s) => (
              <tr key={s.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2 font-medium text-slate-900">{s.name}</td>
                <td className="px-4 py-2 font-mono text-slate-600">{s.slug}</td>
                <td className="px-4 py-2 text-slate-500">
                  {new Date(s.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2 text-right">
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
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
