import { Center, Loader } from "@mantine/core";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import AuditDetailPage from "./pages/AuditDetailPage";
import AuditLogPage from "./pages/AuditLogPage";
import AuditsPage from "./pages/AuditsPage";
import ControlDetailPage from "./pages/ControlDetailPage";
import ControlsPage from "./pages/ControlsPage";
import DashboardPage from "./pages/DashboardPage";
import FrameworksPage from "./pages/FrameworksPage";
import GapAnalysisPage from "./pages/GapAnalysisPage";
import PoliciesPage from "./pages/PoliciesPage";
import PolicyDetailPage from "./pages/PolicyDetailPage";
import ReportsPage from "./pages/ReportsPage";
import RolesPage from "./pages/RolesPage";
import ApiTokensPage from "./pages/ApiTokensPage";
import LoginPage from "./pages/LoginPage";
import AiSearchPage from "./pages/AiSearchPage";
import MyTasksPage from "./pages/MyTasksPage";
import SystemsPage from "./pages/SystemsPage";
import BaselinesPage from "./pages/BaselinesPage";
import ProfilesPage from "./pages/ProfilesPage";
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
        <Route path="/my-tasks" element={<MyTasksPage />} />
        <Route path="/ai-search" element={<AiSearchPage />} />
        <Route path="/risks" element={<RisksPage />} />
        <Route path="/risks/:id" element={<RiskDetailPage />} />
        <Route path="/controls" element={<ControlsPage />} />
        <Route path="/controls/:id" element={<ControlDetailPage />} />
        <Route path="/gap-analysis" element={<GapAnalysisPage />} />
        <Route path="/audits" element={<AuditsPage />} />
        <Route path="/audits/:id" element={<AuditDetailPage />} />
        <Route path="/policies" element={<PoliciesPage />} />
        <Route path="/policies/:id" element={<PolicyDetailPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/audit-log" element={<AuditLogPage />} />
        {user.role === "admin" && <Route path="/systems" element={<SystemsPage />} />}
        {user.role === "admin" && <Route path="/baselines" element={<BaselinesPage />} />}
        {user.role === "admin" && <Route path="/profiles" element={<ProfilesPage />} />}
        {user.role === "admin" && <Route path="/frameworks" element={<FrameworksPage />} />}
        {user.role === "admin" && <Route path="/users" element={<UsersPage />} />}
        {user.role === "admin" && <Route path="/roles" element={<RolesPage />} />}
        {user.role === "admin" && <Route path="/api-tokens" element={<ApiTokensPage />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
