import { useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { useService } from "@/services/ServiceProvider";
import { cn } from "@/lib/cn";

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-full w-full">
      <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-full w-full">
      <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
    </svg>
  );
}

function PeopleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-full w-full">
      <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z" />
    </svg>
  );
}

function PersonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-full w-full">
      <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-full w-full">
      <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" />
    </svg>
  );
}

function BeakerIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-full w-full">
      <path d="M14.5 2.5v6.5l4.5 8H5L9.5 9V2.5h5zm1-1.5H8.5v1H5v1.5h14V2H14.5V1zM5.09 15h13.82L16 9.5V3h-1.5v6.5L17 15H7L9.5 9.5V3H8v6.5L5.09 15z" />
    </svg>
  );
}

function HamburgerIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
    </svg>
  );
}

const PAGE_NAMES: Record<string, string> = {
  "/documents": "Documents",
  "/search": "Search",
  "/playground": "Playground",
  "/members": "Members",
  "/users": "Users",
  "/services": "Services",
};

function SidebarNavItem({
  to,
  icon,
  label,
  onClick,
}: {
  to: string;
  icon: ReactNode;
  label: string;
  onClick?: () => void;
}) {
  return (
    <NavLink to={to} onClick={onClick}>
      {({ isActive }) => (
        <div
          className={cn(
            "flex items-center gap-3 rounded-2xl px-2 py-3 transition-all",
            isActive && "bg-white shadow-sm",
          )}
        >
          <div
            className={cn(
              "flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center rounded-xl shadow-sm",
              isActive ? "bg-teal-300" : "bg-white",
            )}
          >
            <span
              className={cn(
                "flex h-[15px] w-[15px] items-center justify-center",
                isActive ? "text-white" : "text-gray-400",
              )}
            >
              {icon}
            </span>
          </div>
          <span
            className={cn(
              "text-xs font-bold",
              isActive ? "text-[#2D3748]" : "text-[#A0AEC0]",
            )}
          >
            {label}
          </span>
        </div>
      )}
    </NavLink>
  );
}

function SidebarContent({
  isSuperAdmin,
  isServiceAdmin,
  user,
  current,
  logout,
  onNavClick,
}: {
  isSuperAdmin: boolean;
  isServiceAdmin: boolean;
  user: { email: string } | null;
  current: { role: string; name: string } | null;
  logout: () => void;
  onNavClick?: () => void;
}) {
  return (
    <div className="flex h-full flex-col bg-white">
      {/* Logo */}
      <Link
        to="/"
        onClick={onNavClick}
        className="flex items-center gap-3 px-6 py-6"
      >
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-300">
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4 text-white">
            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
          </svg>
        </div>
        <span className="text-sm font-bold text-[#2D3748]">RAGKIT ADMIN</span>
      </Link>

      {/* Divider */}
      <div
        className="mx-6 h-px"
        style={{
          background:
            "linear-gradient(90deg, rgba(224,225,226,0) 0%, rgba(224,225,226,1) 50%, rgba(224,225,226,0.16) 100%)",
        }}
      />

      {/* Nav */}
      <nav className="flex-1 space-y-1 px-4 py-6">
        <SidebarNavItem to="/documents" icon={<FileIcon />} label="Documents" onClick={onNavClick} />
        <SidebarNavItem to="/search" icon={<SearchIcon />} label="Search" onClick={onNavClick} />
        <SidebarNavItem to="/playground" icon={<BeakerIcon />} label="Playground" onClick={onNavClick} />

        {(isServiceAdmin || isSuperAdmin) && (
          <>
            <div className="px-2 pb-1 pt-5">
              <span className="text-[10px] font-bold tracking-widest text-[#2D3748]">
                MANAGEMENT
              </span>
            </div>
            {isServiceAdmin && (
              <SidebarNavItem to="/members" icon={<PeopleIcon />} label="Members" onClick={onNavClick} />
            )}
            {isSuperAdmin && (
              <SidebarNavItem to="/users" icon={<PersonIcon />} label="Users" onClick={onNavClick} />
            )}
            {isSuperAdmin && (
              <SidebarNavItem to="/services" icon={<GearIcon />} label="Services" onClick={onNavClick} />
            )}
          </>
        )}
      </nav>

      {/* User card */}
      <div className="p-4">
        <div className="rounded-2xl bg-gradient-to-br from-teal-400 to-cyan-600 p-4 text-white shadow-md">
          <p className="truncate text-xs font-semibold">{user?.email}</p>
          {current && (
            <p className="mt-0.5 text-xs capitalize opacity-70">
              {current.role} · {current.name}
            </p>
          )}
          <button
            onClick={logout}
            className="mt-3 w-full rounded-xl bg-white/20 py-1.5 text-xs font-semibold backdrop-blur-sm transition-colors hover:bg-white/30"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { services, current, select } = useService();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const isSuperAdmin = user?.is_superadmin ?? false;
  const isServiceAdmin = current?.role === "admin";

  const segment = "/" + (location.pathname.split("/")[1] ?? "");
  const pageName = PAGE_NAMES[segment] ?? "Dashboard";

  const sidebarProps = {
    isSuperAdmin,
    isServiceAdmin,
    user,
    current,
    logout,
  };

  return (
    <div className="flex min-h-screen bg-[#F8F9FA]">
      {/* Desktop sidebar */}
      <aside className="hidden w-[260px] flex-shrink-0 md:block">
        <div className="sticky top-0 h-screen">
          <SidebarContent {...sidebarProps} />
        </div>
      </aside>

      {/* Mobile drawer overlay */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm md:hidden"
          onClick={() => setDrawerOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-[260px] shadow-2xl transition-transform duration-300 md:hidden",
          drawerOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <SidebarContent
          {...sidebarProps}
          onNavClick={() => setDrawerOpen(false)}
        />
      </div>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <header className="flex items-center justify-between px-4 py-4 md:px-8 md:py-5">
          <div className="flex items-center gap-3">
            {/* Hamburger (mobile only) */}
            <button
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-[#2D3748] shadow-sm md:hidden"
              onClick={() => setDrawerOpen(true)}
            >
              <HamburgerIcon />
            </button>
            <div>
              <p className="text-xs text-[#A0AEC0]">Pages / {pageName}</p>
              <h1 className="text-lg font-bold text-[#2D3748] md:text-xl">{pageName}</h1>
            </div>
          </div>

          {services.length > 0 && (
            <div className="flex items-center gap-2">
              <select
                value={current?.id ?? ""}
                onChange={(e) => {
                  const svc = services.find((s) => s.id === Number(e.target.value));
                  if (svc) select(svc);
                }}
                className="rounded-xl border border-gray-200 bg-white px-2 py-2 text-xs font-medium text-[#2D3748] shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-300 md:px-3"
              >
                {services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              {current && (
                <span className="hidden rounded-lg bg-teal-50 px-2 py-1 text-xs font-semibold capitalize text-teal-600 sm:inline">
                  {current.role}
                </span>
              )}
            </div>
          )}
        </header>

        {/* Content */}
        <main className="flex-1 px-4 pb-10 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
