import type { ReactElement } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider";
import { useService } from "@/services/ServiceProvider";

export function RequireAuth({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="p-6 text-slate-500">Loading…</div>;
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

export function RequireServiceAdmin({ children }: { children: ReactElement }) {
  const { current, loading } = useService();
  if (loading) return <div className="p-6 text-slate-500">Loading…</div>;
  if (current?.role !== "admin") {
    return <Navigate to="/documents" replace />;
  }
  return children;
}
