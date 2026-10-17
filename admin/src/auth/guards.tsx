import type { ReactElement } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider";
import { useWorkspace } from "@/workspace/WorkspaceProvider";

export function RequireAuth({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="p-6 text-slate-500">Loading…</div>;
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

export function RequireWorkspaceAdmin({ children }: { children: ReactElement }) {
  const { isWorkspaceAdmin, loading } = useWorkspace();
  if (loading) return <div className="p-6 text-slate-500">Loading…</div>;
  if (!isWorkspaceAdmin) {
    return <Navigate to="/" replace />;
  }
  return children;
}
