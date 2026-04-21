import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { useService } from "@/services/ServiceProvider";

import { cn } from "@/lib/cn";
import { Button } from "./ui";

const NAV_LINK =
  "block rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100";
const NAV_LINK_ACTIVE = "bg-slate-200 text-slate-900";

export default function Layout() {
  const { user, logout } = useAuth();
  const { services, current, select } = useService();
  const isSuperAdmin = user?.is_superadmin ?? false;
  const isServiceAdmin = current?.role === "admin";

  return (
    <div className="flex min-h-full">
      <aside className="hidden w-52 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <Link to="/" className="mb-6 text-lg font-semibold">
          ragkit
        </Link>
        <nav className="space-y-1">
          <NavLink
            to="/documents"
            className={({ isActive }) => cn(NAV_LINK, isActive && NAV_LINK_ACTIVE)}
          >
            Documents
          </NavLink>
          <NavLink
            to="/search"
            className={({ isActive }) => cn(NAV_LINK, isActive && NAV_LINK_ACTIVE)}
          >
            Search
          </NavLink>
          {isServiceAdmin && (
            <NavLink
              to="/members"
              className={({ isActive }) => cn(NAV_LINK, isActive && NAV_LINK_ACTIVE)}
            >
              Members
            </NavLink>
          )}
          {isSuperAdmin && (
            <NavLink
              to="/services"
              className={({ isActive }) => cn(NAV_LINK, isActive && NAV_LINK_ACTIVE)}
            >
              Services
            </NavLink>
          )}
        </nav>
      </aside>
      <main className="flex-1 overflow-x-auto">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <div className="flex items-center gap-3">
            {services.length > 0 && (
              <select
                value={current?.id ?? ""}
                onChange={(e) => {
                  const svc = services.find((s) => s.id === Number(e.target.value));
                  if (svc) select(svc);
                }}
                className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-400"
              >
                {services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            )}
            {current && (
              <span className="text-xs text-slate-400 capitalize">{current.role}</span>
            )}
          </div>
          <div className="flex items-center gap-4">
            {user && (
              <span className="text-sm text-slate-600">
                <span className="font-medium">{user.email}</span>
              </span>
            )}
            <Button variant="secondary" size="sm" onClick={logout}>
              Log out
            </Button>
          </div>
        </header>
        <div className="px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
