import {
  Users,
  Landmark,
  ShieldAlert,
  AlertTriangle,
  TrendingUp,
  IndianRupee,
} from "lucide-react";
import { StatCard } from "@/components/ui";
import { RecentAlerts } from "./RecentAlerts";
import { QuickActions } from "./QuickActions";
import { RiskOverview } from "./RiskOverview";

export function DashboardPage() {
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

      {/* ── KPI cards ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Active Profiles"
          value="128"
          subtitle="12 added this month"
          icon={<Users className="h-5 w-5" />}
          trend={{ value: 9.4, positive: true }}
        />
        <StatCard
          label="Active Loans"
          value="342"
          subtitle="₹4.7 Cr outstanding"
          icon={<Landmark className="h-5 w-5" />}
        />
        <StatCard
          label="Avg Risk Score"
          value="412"
          subtitle="Medium risk band"
          icon={<ShieldAlert className="h-5 w-5" />}
          trend={{ value: 2.1, positive: false }}
        />
        <StatCard
          label="Active Alerts"
          value="17"
          subtitle="3 critical"
          icon={<AlertTriangle className="h-5 w-5" />}
          trend={{ value: 14, positive: false }}
        />
      </div>

      {/* ── Second row ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total Disbursed"
          value="₹8.2 Cr"
          subtitle="Last 12 months"
          icon={<IndianRupee className="h-5 w-5" />}
        />
        <StatCard
          label="Repayment Rate"
          value="91.3%"
          subtitle="On-time repayments"
          icon={<TrendingUp className="h-5 w-5" />}
          trend={{ value: 3.2, positive: true }}
        />
        <StatCard
          label="Guidance Issued"
          value="89"
          subtitle="This quarter"
          icon={<TrendingUp className="h-5 w-5" />}
        />
        <StatCard
          label="Default Rate"
          value="4.2%"
          subtitle="Below industry avg"
          icon={<ShieldAlert className="h-5 w-5" />}
          trend={{ value: 1.1, positive: true }}
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
