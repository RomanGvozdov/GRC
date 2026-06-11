import { Center, Loader } from "@mantine/core";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import AuditLogPage from "./pages/AuditLogPage";
import ControlDetailPage from "./pages/ControlDetailPage";
import ControlsPage from "./pages/ControlsPage";
import DashboardPage from "./pages/DashboardPage";
import GapAnalysisPage from "./pages/GapAnalysisPage";
import LoginPage from "./pages/LoginPage";
import RiskDetailPage from "./pages/RiskDetailPage";
import RisksPage from "./pages/RisksPage";
import UsersPage from "./pages/UsersPage";

export default function App() {
  const { user, loading } = useAuth();

  if (loading)
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    );

  if (!user)
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );

  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/risks" element={<RisksPage />} />
        <Route path="/risks/:id" element={<RiskDetailPage />} />
        <Route path="/controls" element={<ControlsPage />} />
        <Route path="/controls/:id" element={<ControlDetailPage />} />
        <Route path="/gap-analysis" element={<GapAnalysisPage />} />
        <Route path="/audit-log" element={<AuditLogPage />} />
        {user.role === "admin" && <Route path="/users" element={<UsersPage />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
