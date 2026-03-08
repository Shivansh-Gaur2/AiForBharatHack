import { Routes, Route } from "react-router-dom";
import { AppShell } from "@/components/layout";
import { LoginPage, ProtectedRoute } from "@/features/auth";
import { DashboardPage } from "@/features/dashboard";
import { ProfileListPage, ProfileDetailPage, CreateProfilePage } from "@/features/profiles";
import { LoanListPage, LoanDetailPage, CreateLoanPage } from "@/features/loans";
import { RiskPage } from "@/features/risk";
import { CashFlowPage } from "@/features/cashflow";
import { AlertsPage, ScenarioPage } from "@/features/alerts";
import { GuidancePage } from "@/features/guidance";
import { SecurityPage } from "@/features/security";
import { AIAdvisorPage } from "@/features/advisor";

export function App() {
  return (
    <Routes>
      {/* Public route — Login */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected routes — require authentication */}
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        {/* Dashboard */}
        <Route index element={<DashboardPage />} />

        {/* Profiles */}
        <Route path="profiles" element={<ProfileListPage />} />
        <Route path="profiles/new" element={<CreateProfilePage />} />
        <Route path="profiles/:profileId" element={<ProfileDetailPage />} />

        {/* Loans */}
        <Route path="loans" element={<LoanListPage />} />
        <Route path="loans/new" element={<CreateLoanPage />} />
        <Route path="loans/:trackingId" element={<LoanDetailPage />} />

        {/* Risk Assessment */}
        <Route path="risk" element={<RiskPage />} />

        {/* Cash Flow */}
        <Route path="cashflow" element={<CashFlowPage />} />

        {/* Alerts & Scenarios */}
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="alerts/scenarios" element={<ScenarioPage />} />

        {/* Guidance */}
        <Route path="guidance" element={<GuidancePage />} />

        {/* Security */}
        <Route path="security" element={<SecurityPage />} />

        {/* AI Advisor */}
        <Route path="advisor" element={<AIAdvisorPage />} />

        {/* Fallback */}
        <Route
          path="*"
          element={
            <div className="flex h-96 items-center justify-center">
              <div className="text-center">
                <h2 className="text-2xl font-bold text-gray-900">404</h2>
                <p className="mt-1 text-sm text-gray-500">Page not found</p>
              </div>
            </div>
          }
        />
      </Route>
    </Routes>
  );
}
