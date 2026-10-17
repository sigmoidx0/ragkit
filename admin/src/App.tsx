import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import Layout from "./components/Layout";
import { RequireAuth, RequireWorkspaceAdmin } from "./auth/guards";
import { WorkspaceProvider } from "./workspace/WorkspaceProvider";
import LoginPage from "./pages/LoginPage";
import AgentHomePage from "./pages/AgentHomePage";
import ChatPage from "./pages/ChatPage";
import DocumentsPage from "./pages/DocumentsPage";
import DocumentDetailPage from "./pages/DocumentDetailPage";
import DocumentSetsPage from "./pages/DocumentSetsPage";
import AgentSettingsPage from "./pages/AgentSettingsPage";
import RetrievalLabPage from "./pages/RetrievalLabPage";
import EvalPage from "./pages/EvalPage";
import McpServersPage from "./pages/McpServersPage";
import MembersPage from "./pages/MembersPage";
import UsersPage from "./pages/UsersPage";
import WorkspacesPage from "./pages/WorkspacesPage";

export default function App() {
  return (
    <>
    <Toaster richColors position="top-right" />
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <WorkspaceProvider>
              <Layout />
            </WorkspaceProvider>
          </RequireAuth>
        }
      >
        {/* Use */}
        <Route index element={<AgentHomePage />} />
        <Route path="/chat" element={<ChatPage />} />
        {/* Knowledge */}
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/:id" element={<DocumentDetailPage />} />
        <Route path="/document-sets" element={<DocumentSetsPage />} />
        {/* Build */}
        <Route path="/agent-settings" element={<RequireWorkspaceAdmin><AgentSettingsPage /></RequireWorkspaceAdmin>} />
        <Route path="/lab" element={<Navigate to="/lab/search" replace />} />
        <Route path="/lab/:tab" element={<RetrievalLabPage />} />
        <Route path="/evals" element={<RequireWorkspaceAdmin><EvalPage /></RequireWorkspaceAdmin>} />
        <Route path="/mcp" element={<RequireWorkspaceAdmin><McpServersPage /></RequireWorkspaceAdmin>} />
        {/* Admin */}
        <Route path="/members" element={<RequireWorkspaceAdmin><MembersPage /></RequireWorkspaceAdmin>} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/workspaces" element={<WorkspacesPage />} />
        {/* Old addresses, kept so bookmarks still land somewhere sensible */}
        <Route path="/search" element={<Navigate to="/lab/search" replace />} />
        <Route path="/pipeline" element={<Navigate to="/lab/pipelines" replace />} />
        <Route path="/playground" element={<Navigate to="/lab/chunking" replace />} />
        <Route path="/services" element={<Navigate to="/workspaces" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </>
  );
}
