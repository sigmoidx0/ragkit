import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import Layout from "./components/Layout";
import { RequireAuth, RequireServiceAdmin } from "./auth/guards";
import { ServiceProvider } from "./services/ServiceProvider";
import LoginPage from "./pages/LoginPage";
import DocumentsPage from "./pages/DocumentsPage";
import DocumentDetailPage from "./pages/DocumentDetailPage";
import SearchPage from "./pages/SearchPage";
import ServicesPage from "./pages/ServicesPage";
import MembersPage from "./pages/MembersPage";
import UsersPage from "./pages/UsersPage";
import PlaygroundPage from "./pages/PlaygroundPage";
import PipelineBuilderPage from "./pages/PipelineBuilderPage";
import ChatPage from "./pages/ChatPage";
import AgentHomePage from "./pages/AgentHomePage";
import AgentSettingsPage from "./pages/AgentSettingsPage";
import EvalPage from "./pages/EvalPage";

export default function App() {
  return (
    <>
    <Toaster richColors position="top-right" />
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <ServiceProvider>
              <Layout />
            </ServiceProvider>
          </RequireAuth>
        }
      >
        <Route index element={<AgentHomePage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/:id" element={<DocumentDetailPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/services" element={<ServicesPage />} />
        <Route path="/members" element={<MembersPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/playground" element={<RequireServiceAdmin><PlaygroundPage /></RequireServiceAdmin>} />
        <Route path="/pipeline" element={<PipelineBuilderPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/evals" element={<RequireServiceAdmin><EvalPage /></RequireServiceAdmin>} />
        <Route path="/agent-settings" element={<RequireServiceAdmin><AgentSettingsPage /></RequireServiceAdmin>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </>
  );
}
