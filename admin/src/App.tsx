import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import Layout from "./components/Layout";
import { RequireAuth } from "./auth/guards";
import { ServiceProvider } from "./services/ServiceProvider";
import LoginPage from "./pages/LoginPage";
import DocumentsPage from "./pages/DocumentsPage";
import DocumentDetailPage from "./pages/DocumentDetailPage";
import SearchPage from "./pages/SearchPage";
import ServicesPage from "./pages/ServicesPage";
import MembersPage from "./pages/MembersPage";
import UsersPage from "./pages/UsersPage";
import ChunkPlaygroundPage from "./pages/ChunkPlaygroundPage";

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
        <Route index element={<Navigate to="/documents" replace />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/:id" element={<DocumentDetailPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/services" element={<ServicesPage />} />
        <Route path="/members" element={<MembersPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/chunk-playground" element={<ChunkPlaygroundPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </>
  );
}
