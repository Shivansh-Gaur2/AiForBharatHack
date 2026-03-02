import {
  Users,
  Landmark,
  ShieldAlert,
  AlertTriangle,
  TrendingUp,
  IndianRupee,
  Loader2,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { StatCard } from "@/components/ui";
import { dashboardApi } from "@/api/dashboard";
import { RecentAlerts } from "./RecentAlerts";
import { QuickActions } from "./QuickActions";
import { RiskOverview } from "./RiskOverview";

function formatCurrency(value: number): string {
  if (value >= 1_00_00_000) return `₹${(value / 1_00_00_000).toFixed(1)} Cr`;
  if (value >= 1_00_000) return `₹${(value / 1_00_000).toFixed(1)} L`;
  if (value >= 1_000) return `₹${(value / 1_000).toFixed(1)} K`;
  return `₹${value.toFixed(0)}`;
}

function riskBand(score: number): string {
  if (score <= 300) return "Low risk band";
  if (score <= 500) return "Medium risk band";
  if (score <= 700) return "High risk band";
  return "Very high risk band";
}

export function DashboardPage() {
  const profileStats = useQuery({
    queryKey: ["dashboard", "profiles"],
    queryFn: dashboardApi.profileStats,
    staleTime: 60_000,
  });

  const loanStats = useQuery({
    queryKey: ["dashboard", "loans"],
    queryFn: dashboardApi.loanStats,
    staleTime: 60_000,
  });

  const riskStats = useQuery({
    queryKey: ["dashboard", "risk"],
    queryFn: dashboardApi.riskStats,
    staleTime: 60_000,
  });

  const alertStats = useQuery({
    queryKey: ["dashboard", "alerts"],
    queryFn: dashboardApi.alertStats,
    staleTime: 60_000,
  });

  const guidanceStats = useQuery({
    queryKey: ["dashboard", "guidance"],
    queryFn: dashboardApi.guidanceStats,
    staleTime: 60_000,
  });

  const isLoading =
    profileStats.isLoading ||
    loanStats.isLoading ||
    riskStats.isLoading ||
    alertStats.isLoading ||
    guidanceStats.isLoading;

  return (
    <div className="space-y-6">
      {/* ── Welcome banner ─────────────────────────────────── */}
      <div className="rounded-xl bg-gradient-to-r from-brand-600 to-brand-700 p-6 text-white shadow-lg">
        <h2 className="text-xl font-bold">Welcome to Rural Credit Advisor</h2>
        <p className="mt-1 text-sm text-brand-100">
          AI-powered credit decision support for rural India. Monitor
          borrowers, assess risk, and generate personalized guidance.
        </p>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading dashboard data…
        </div>
      )}

      {/* ── KPI cards ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Active Profiles"
          value={String(profileStats.data?.total_profiles ?? "–")}
          subtitle={`${profileStats.data?.recent_count ?? 0} added this month`}
          icon={<Users className="h-5 w-5" />}
        />
        <StatCard
          label="Active Loans"
          value={String(loanStats.data?.active_loans ?? "–")}
          subtitle={`${formatCurrency(loanStats.data?.total_outstanding ?? 0)} outstanding`}
          icon={<Landmark className="h-5 w-5" />}
        />
        <StatCard
          label="Avg Risk Score"
          value={String(riskStats.data?.avg_risk_score ?? "–")}
          subtitle={riskBand(riskStats.data?.avg_risk_score ?? 0)}
          icon={<ShieldAlert className="h-5 w-5" />}
        />
        <StatCard
          label="Active Alerts"
          value={String(alertStats.data?.active_alerts ?? "–")}
          subtitle={`${alertStats.data?.severity_counts?.CRITICAL ?? 0} critical`}
          icon={<AlertTriangle className="h-5 w-5" />}
        />
      </div>

      {/* ── Second row ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total Disbursed"
          value={formatCurrency(loanStats.data?.total_disbursed ?? 0)}
          subtitle="All time"
          icon={<IndianRupee className="h-5 w-5" />}
        />
        <StatCard
          label="Repayment Rate"
          value={`${loanStats.data?.avg_repayment_rate ?? 0}%`}
          subtitle="On-time repayments"
          icon={<TrendingUp className="h-5 w-5" />}
        />
        <StatCard
          label="Guidance Issued"
          value={String(guidanceStats.data?.total_issued ?? "–")}
          subtitle={`${guidanceStats.data?.active_count ?? 0} active`}
          icon={<TrendingUp className="h-5 w-5" />}
        />
        <StatCard
          label="Default Rate"
          value={`${loanStats.data?.default_rate ?? 0}%`}
          subtitle={`${loanStats.data?.default_count ?? 0} defaults`}
          icon={<ShieldAlert className="h-5 w-5" />}
        />
      </div>

      {/* ── Main content grid ──────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <RecentAlerts />
        </div>
        <div className="space-y-6">
          <QuickActions />
          <RiskOverview />
        </div>
      </div>
    </div>
  );
}
