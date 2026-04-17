import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { cn } from "@/lib/cn";
import { Button } from "./ui";

const NAV_LINK =
  "block rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100";
const NAV_LINK_ACTIVE = "bg-slate-200 text-slate-900";

export default function Layout() {
  const { user, logout } = useAuth();
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
        </nav>
      </aside>
      <main className="flex-1 overflow-x-auto">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <div className="text-sm text-slate-600">
            {user ? (
              <span>
                Signed in as <span className="font-medium">{user.email}</span>
              </span>
            ) : null}
          </div>
          <Button variant="secondary" size="sm" onClick={logout}>
            Log out
          </Button>
        </header>
        <div className="px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
