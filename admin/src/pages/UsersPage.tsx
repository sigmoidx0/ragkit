import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { UsersApi } from "@/api/endpoints";
import { Button, Card, Input, Label } from "@/components/ui";
import { DataTable, type Column } from "@/components/DataTable";
import type { User } from "@/api/types";

export default function UsersPage() {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const listQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => UsersApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: () => UsersApi.create(email, password),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["users"] });
      setEmail("");
      setPassword("");
      toast.success("User created");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to create user"),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMutation.mutate();
  };

  const users = listQuery.data ?? [];

  const USER_COLUMNS: Column<User>[] = [
    { header: "Email", render: (u) => <span className="text-[#2D3748]">{u.email}</span> },
    {
      header: "Created",
      render: (u) => <span className="text-[#A0AEC0]">{new Date(u.created_at).toLocaleString()}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Users</h1>

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#A0AEC0]">
          New User
        </h2>
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="user-email">Email</Label>
            <Input
              id="user-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              required
            />
          </div>
          <div>
            <Label htmlFor="user-password">Password</Label>
            <Input
              id="user-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="min. 8 characters"
              minLength={8}
              required
            />
          </div>
          <div className="md:col-span-2">
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating…" : "Create User"}
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <DataTable<User>
          columns={USER_COLUMNS}
          rows={users}
          rowKey={(u) => u.id}
          isLoading={listQuery.isLoading}
          emptyMessage="No users yet."
        />
      </Card>
    </div>
  );
}
