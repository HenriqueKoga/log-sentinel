import { Route, Routes, Navigate } from "react-router-dom";
import { LoginPage } from "../features/auth/LoginPage";
import { SignupPage } from "../features/auth/SignupPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { AppLayout } from "../shared/components/AppLayout";
import { useAuth } from "./providers/useAuth";
import { ProjectsPage } from "../features/projects/ProjectsPage";
import { ProjectTokensPage } from "../features/projects/ProjectTokensPage";
import { TokensPage } from "../features/tokens/TokensPage";
import { LogsPage } from "../features/logs/LogsPage";
import { IssuesListPage } from "../features/issues/IssuesListPage";
import { IssueDetailPage } from "../features/issues/IssueDetailPage";
import { AlertsPage } from "../features/alerts/AlertsPage";
import { BillingPage } from "../features/billing/BillingPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { FixSuggestionsPage } from "../features/ai-insights/FixSuggestionsPage";
import { LogChatPage } from "../features/chat/LogChatPage";

export const AppRoutes = () => {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/issues" element={<IssuesListPage />} />
        <Route path="/issues/:issueId" element={<IssueDetailPage />} />
        <Route path="/ai" element={<FixSuggestionsPage />} />
        <Route path="/chat" element={<LogChatPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/tokens" element={<TokensPage />} />
        <Route path="/projects/:projectId/tokens" element={<ProjectTokensPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/billing" element={<BillingPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

