import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ServicesApi, UsersApi } from "@/api/endpoints";
import { Button, Card, Label, Select } from "@/components/ui";
import { DataTable, type Column } from "@/components/DataTable";
import { useService } from "@/services/ServiceProvider";
import type { ServiceMember, ServiceRole } from "@/api/types";

const ROLES: ServiceRole[] = ["admin", "member", "viewer"];

export default function MembersPage() {
  const qc = useQueryClient();
  const { current: service } = useService();

  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [selectedRole, setSelectedRole] = useState<ServiceRole>("member");

  const membersQuery = useQuery({
    queryKey: ["members", service?.id],
    queryFn: () => ServicesApi.listMembers(service!.id),
    enabled: service != null,
  });

  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => UsersApi.list(),
  });

  const addMutation = useMutation({
    mutationFn: () => ServicesApi.addMember(service!.id, Number(selectedUserId), selectedRole),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["members", service?.id] });
      setSelectedUserId("");
      setSelectedRole("member");
      toast.success("Member added");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to add member"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: ServiceRole }) =>
      ServicesApi.updateMember(service!.id, userId, role),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["members", service?.id] });
      toast.success("Role updated");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to update role"),
  });

  const removeMutation = useMutation({
    mutationFn: (userId: number) => ServicesApi.removeMember(service!.id, userId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["members", service?.id] });
      toast.success("Member removed");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to remove member"),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!selectedUserId) return;
    addMutation.mutate();
  };

  const members = membersQuery.data ?? [];
  const users = usersQuery.data ?? [];
  const memberUserIds = new Set(members.map((m) => m.user_id));
  const availableUsers = users.filter((u) => !memberUserIds.has(u.id));

  const MEMBER_COLUMNS: Column<ServiceMember>[] = [
    {
      header: "Email",
      render: (m) => (
        <span className="text-[#2D3748]">
          {users.find((u) => u.id === m.user_id)?.email ?? `#${m.user_id}`}
        </span>
      ),
    },
    {
      header: "Role",
      render: (m) => (
        <Select
          value={m.role}
          onChange={(e) =>
            updateMutation.mutate({ userId: m.user_id, role: e.target.value as ServiceRole })
          }
          className="w-32"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </Select>
      ),
    },
    {
      header: "",
      className: "text-right",
      render: (m) => (
        <Button
          variant="danger"
          size="sm"
          disabled={removeMutation.isPending}
          onClick={() => {
            const email = users.find((u) => u.id === m.user_id)?.email ?? `#${m.user_id}`;
            if (confirm(`Remove ${email} from this service?`)) {
              removeMutation.mutate(m.user_id);
            }
          }}
        >
          Remove
        </Button>
      ),
    },
  ];

  if (!service) return <div className="text-[#A0AEC0]">No service selected.</div>;

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#A0AEC0]">
          Add Member — {service.name}
        </h2>
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-3">
          <div className="md:col-span-2">
            <Label htmlFor="user-select">User</Label>
            <Select
              id="user-select"
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              required
            >
              <option value="">Select a user…</option>
              {availableUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.email}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="role-select">Role</Label>
            <Select
              id="role-select"
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value as ServiceRole)}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </Select>
          </div>
          <div className="md:col-span-3">
            <Button type="submit" disabled={addMutation.isPending || !selectedUserId}>
              {addMutation.isPending ? "Adding…" : "Add Member"}
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <DataTable<ServiceMember>
          columns={MEMBER_COLUMNS}
          rows={members}
          rowKey={(m) => m.user_id}
          isLoading={membersQuery.isLoading}
          emptyMessage="No members yet."
        />
      </Card>
    </div>
  );
}
