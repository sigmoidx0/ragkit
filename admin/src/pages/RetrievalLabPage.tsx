import { NavLink, Navigate, useParams } from "react-router-dom";

import { cn } from "@/lib/cn";
import PipelineBuilderPage from "@/pages/PipelineBuilderPage";
import PlaygroundPage from "@/pages/PlaygroundPage";
import SearchPage from "@/pages/SearchPage";
import { useWorkspace } from "@/workspace/WorkspaceProvider";

type LabTab = "search" | "pipelines" | "chunking";

const TABS: { key: LabTab; label: string; hint: string; adminOnly?: boolean }[] = [
  { key: "search", label: "Search", hint: "Query the workspace and inspect what comes back" },
  { key: "pipelines", label: "Pipelines", hint: "Build retrieval pipelines agents can use" },
  { key: "chunking", label: "Chunking", hint: "Preview how a file splits before uploading it", adminOnly: true },
];

/**
 * Tools for seeing how retrieval behaves — the experiments behind an agent's
 * answers. Each tab is a page of its own; this just groups them.
 */
export default function RetrievalLabPage() {
  const { tab = "search" } = useParams<{ tab: LabTab }>();
  const { isWorkspaceAdmin, loading } = useWorkspace();
  // Until the workspace loads, the role is unknown — don't bounce an admin
  // off the admin-only tab they asked for.
  if (loading) return <div className="h-96 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800" />;
  const visible = TABS.filter((t) => !t.adminOnly || isWorkspaceAdmin);
  const current = visible.find((t) => t.key === tab);
  if (!current) return <Navigate to="/lab/search" replace />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-1 rounded-2xl border border-gray-100 bg-white p-1 shadow-sm dark:border-gray-700 dark:bg-gray-800">
        {visible.map((t) => (
          <NavLink
            key={t.key}
            to={`/lab/${t.key}`}
            title={t.hint}
            className={({ isActive }) =>
              cn(
                "rounded-xl px-4 py-2 text-sm transition-colors",
                isActive
                  ? "bg-teal-500 font-semibold text-white"
                  : "text-gray-500 hover:bg-gray-50 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-700",
              )
            }
          >
            {t.label}
          </NavLink>
        ))}
        <span className="ml-auto hidden pr-3 text-xs text-gray-400 md:block">{current.hint}</span>
      </div>
      {tab === "search" && <SearchPage />}
      {tab === "pipelines" && <PipelineBuilderPage />}
      {tab === "chunking" && <PlaygroundPage />}
    </div>
  );
}
