import { useState, useEffect, useRef, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { useWorkspace } from "@/workspace/WorkspaceProvider";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/cn";
import { getAgentTheme } from "@/lib/agentTheme";
import type { WorkspaceWithRole } from "@/api/types";

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-full w-full">
      <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" />
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

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-full w-full">
      <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" />
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

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58c-.39-.39-1.03-.39-1.41 0-.39.39-.39 1.03 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0 .38-.39.39-1.03 0-1.41L5.99 4.58zm12.37 12.37c-.39-.39-1.03-.39-1.41 0-.39.39-.39 1.03 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0 .39-.38.39-1.02 0-1.41l-1.06-1.06zm1.06-12.37l-1.06 1.06c-.39.39-.39 1.03 0 1.41.39.39 1.03.39 1.41 0l1.06-1.06c.39-.39.39-1.03 0-1.41-.38-.39-1.02-.39-1.41 0zM7.05 18.36l-1.06 1.06c-.39.39-.39 1.03 0 1.41.39.39 1.03.39 1.41 0l1.06-1.06c.39-.39.39-1.03 0-1.41-.39-.38-1.03-.39-1.41 0z" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zm5.6 8H19v6h-2.8v-6z" />
    </svg>
  );
}

function GridIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M3 3h8v8H3V3zm10 0h8v8h-8V3zM3 13h8v8H3v-8zm10 0h8v8h-8v-8z" />
    </svg>
  );
}

function SlidersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z" />
    </svg>
  );
}

function PlugIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M16 7V3h-2v4h-4V3H8v4H7a1 1 0 0 0-1 1v4a6 6 0 0 0 5 5.91V22h2v-4.09A6 6 0 0 0 18 12V8a1 1 0 0 0-1-1h-1z" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9c0-.46-.04-.92-.1-1.36-.98 1.37-2.58 2.26-4.4 2.26-2.98 0-5.4-2.42-5.4-5.4 0-1.81.89-3.42 2.26-4.4-.44-.06-.9-.1-1.36-.1z" />
    </svg>
  );
}

function ChevronDownIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
    >
      <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z" />
    </svg>
  );
}

/** Picks the workspace whose agents, documents and members the app shows. */
function WorkspaceSwitcher({
  workspaces,
  current,
  select,
}: {
  workspaces: WorkspaceWithRole[];
  current: WorkspaceWithRole | null;
  select: (w: WorkspaceWithRole) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const theme = current ? getAgentTheme(current) : null;

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);

  return (
    <div ref={ref} className="relative px-4 py-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 rounded-2xl border border-gray-100 bg-white px-3 py-2.5 shadow-sm transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-700"
      >
        <div
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl text-lg"
          style={{ backgroundColor: theme ? theme.accent + "22" : "#14B8A622" }}
        >
          {theme?.icon ?? "🤖"}
        </div>
        <div className="flex-1 min-w-0 text-left">
          <p className="truncate text-xs font-bold text-[#2D3748] dark:text-gray-100">
            {current?.name ?? "Select a workspace"}
          </p>
          {current && (
            <p className="text-[10px] text-[#A0AEC0]">Workspace · <span className="capitalize">{current.role}</span></p>
          )}
        </div>
        {workspaces.length > 1 && (
          <span className="text-[#A0AEC0]">
            <ChevronDownIcon open={open} />
          </span>
        )}
      </button>

      {open && workspaces.length > 1 && (
        <div className="absolute left-4 right-4 top-full z-50 mt-1 overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-800">
          {workspaces.map((s) => {
            const t = getAgentTheme(s);
            const isSelected = s.id === current?.id;
            return (
              <button
                key={s.id}
                onClick={() => { select(s); setOpen(false); }}
                className={cn(
                  "flex w-full items-center gap-3 px-3 py-2.5 transition-colors",
                  isSelected
                    ? "bg-gray-50 dark:bg-gray-700"
                    : "hover:bg-gray-50 dark:hover:bg-gray-700",
                )}
              >
                <div
                  className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl text-base"
                  style={{ backgroundColor: t.accent + "22" }}
                >
                  {t.icon}
                </div>
                <div className="flex-1 min-w-0 text-left">
                  <p className="truncate text-xs font-semibold text-[#2D3748] dark:text-gray-100">{s.name}</p>
                  <p className="text-[10px] capitalize text-[#A0AEC0]">{s.role}</p>
                </div>
                {isSelected && (
                  <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

const PAGE_NAMES: Record<string, string> = {
  "/": "Agents",
  "/chat": "Chat",
  "/documents": "Documents",
  "/document-sets": "Document Sets",
  "/agent-settings": "Agent Settings",
  "/lab": "Retrieval Lab",
  "/evals": "Evaluate",
  "/mcp": "MCP Servers",
  "/members": "Members",
  "/users": "Users",
  "/workspaces": "Workspaces",
};

function NavGroup({ label }: { label: string }) {
  return (
    <div className="px-2 pb-1 pt-3 first:pt-1">
      <span className="text-[10px] font-bold tracking-widest text-[#A0AEC0] dark:text-gray-500">{label}</span>
    </div>
  );
}

function FolderIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z" />
    </svg>
  );
}

function SidebarNavItem({
  to,
  icon,
  label,
  onClick,
  end,
}: {
  to: string;
  icon: ReactNode;
  label: string;
  onClick?: () => void;
  /** Match the path exactly — needed for "/", which every route starts with. */
  end?: boolean;
}) {
  return (
    <NavLink to={to} end={end} onClick={onClick}>
      {({ isActive }) => (
        <div
          className={cn(
            "flex items-center gap-3 rounded-2xl px-2 py-1.5 transition-all",
            isActive && "bg-white shadow-sm dark:bg-gray-700",
          )}
        >
          <div
            className={cn(
              "flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center rounded-xl shadow-sm",
              isActive ? "bg-teal-300" : "bg-white dark:bg-gray-600",
            )}
          >
            <span
              className={cn(
                "flex h-[15px] w-[15px] items-center justify-center",
                isActive ? "text-white" : "text-gray-400 dark:text-gray-300",
              )}
            >
              {icon}
            </span>
          </div>
          <span
            className={cn(
              "text-xs font-bold",
              isActive ? "text-[#2D3748] dark:text-gray-100" : "text-[#A0AEC0] dark:text-gray-400",
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
  isWorkspaceAdmin,
  user,
  workspaces,
  current,
  select,
  logout,
  onNavClick,
}: {
  isSuperAdmin: boolean;
  isWorkspaceAdmin: boolean;
  user: { email: string } | null;
  workspaces: WorkspaceWithRole[];
  current: WorkspaceWithRole | null;
  select: (w: WorkspaceWithRole) => void;
  logout: () => void;
  onNavClick?: () => void;
}) {
  const theme = current ? getAgentTheme(current) : null;

  return (
    <div className="flex h-full flex-col bg-white dark:bg-gray-800">
      {/* Logo */}
      <Link
        to="/"
        onClick={onNavClick}
        className="flex items-center gap-3 px-6 py-5"
      >
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-300">
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4 text-white">
            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
          </svg>
        </div>
        <span className="text-sm font-bold text-[#2D3748] dark:text-gray-100">RAGKIT ADMIN</span>
      </Link>

      {/* Workspace switcher */}
      {workspaces.length > 0 && <WorkspaceSwitcher workspaces={workspaces} current={current} select={select} />}

      {/* Divider */}
      <div className="mx-6 h-px bg-gray-200 dark:bg-gray-700" />

      {/* Nav — grouped by what you're doing: using agents, curating what they
          know, building and measuring them, administering who gets in. */}
      <nav className="flex-1 overflow-y-auto px-4 py-2">
        <NavGroup label="USE" />
        <SidebarNavItem to="/" end icon={<GridIcon />} label="Agents" onClick={onNavClick} />
        <SidebarNavItem to="/chat" icon={<ChatIcon />} label="Chat" onClick={onNavClick} />

        <NavGroup label="KNOWLEDGE" />
        <SidebarNavItem to="/documents" icon={<FileIcon />} label="Documents" onClick={onNavClick} />
        <SidebarNavItem to="/document-sets" icon={<FolderIcon />} label="Document Sets" onClick={onNavClick} />

        <NavGroup label="BUILD" />
        {isWorkspaceAdmin && (
          <SidebarNavItem to="/agent-settings" icon={<SlidersIcon />} label="Agent Settings" onClick={onNavClick} />
        )}
        {isWorkspaceAdmin && (
          <SidebarNavItem to="/mcp" icon={<PlugIcon />} label="MCP Servers" onClick={onNavClick} />
        )}
        <SidebarNavItem to="/lab" icon={<BeakerIcon />} label="Retrieval Lab" onClick={onNavClick} />
        {isWorkspaceAdmin && (
          <SidebarNavItem to="/evals" icon={<ChartIcon />} label="Evaluate" onClick={onNavClick} />
        )}

        {(isWorkspaceAdmin || isSuperAdmin) && <NavGroup label="ADMIN" />}
        {isWorkspaceAdmin && (
          <SidebarNavItem to="/members" icon={<PeopleIcon />} label="Members" onClick={onNavClick} />
        )}
        {isSuperAdmin && <SidebarNavItem to="/users" icon={<PersonIcon />} label="Users" onClick={onNavClick} />}
        {isSuperAdmin && (
          <SidebarNavItem to="/workspaces" icon={<GearIcon />} label="Workspaces" onClick={onNavClick} />
        )}
      </nav>

      {/* User card */}
      <div className="p-4">
        <div
          className="rounded-2xl p-4 text-white shadow-md"
          style={{
            background: theme
              ? `linear-gradient(135deg, ${theme.gradientFrom}, ${theme.gradientTo})`
              : "linear-gradient(135deg, #2DD4BF, #06B6D4)",
          }}
        >
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
  const { workspaces, workspace: current, selectWorkspace: select, isWorkspaceAdmin } = useWorkspace();
  const { theme, toggle } = useTheme();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const isSuperAdmin = user?.is_superadmin ?? false;

  const segment = "/" + (location.pathname.split("/")[1] ?? "");
  const pageName = PAGE_NAMES[segment] ?? "Dashboard";

  const sidebarProps = {
    isSuperAdmin,
    isWorkspaceAdmin,
    user,
    workspaces,
    current,
    select,
    logout,
  };

  return (
    <div className="flex min-h-screen bg-[#F8F9FA] dark:bg-gray-900">
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
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-[#2D3748] shadow-sm dark:bg-gray-700 dark:text-gray-100 md:hidden"
              onClick={() => setDrawerOpen(true)}
            >
              <HamburgerIcon />
            </button>
            <div>
              <p className="text-xs text-[#A0AEC0]">Pages / {pageName}</p>
              <h1 className="text-lg font-bold text-[#2D3748] dark:text-gray-100 md:text-xl">{pageName}</h1>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Theme toggle */}
            <button
              onClick={toggle}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-[#2D3748] shadow-sm transition-colors hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600"
              aria-label="Toggle theme"
            >
              {theme === "light" ? <MoonIcon /> : <SunIcon />}
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 px-4 pb-10 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
