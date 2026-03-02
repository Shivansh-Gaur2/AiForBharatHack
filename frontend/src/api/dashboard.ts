import { httpClient } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ProfileStats {
  total_profiles: number;
  recent_count: number;
  occupation_breakdown: Record<string, number>;
}

export interface LoanStats {
  active_loans: number;
  total_loans: number;
  total_outstanding: number;
  total_disbursed: number;
  avg_repayment_rate: number;
  default_count: number;
  default_rate: number;
}

export interface RiskStats {
  avg_risk_score: number;
  total_assessments: number;
  distribution: Record<string, number>;
}

export interface RecentAlert {
  alert_id: string;
  profile_id: string;
  alert_type: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  status: string;
  title: string;
  description: string;
  created_at: string;
}

export interface AlertStats {
  total_alerts: number;
  active_alerts: number;
  severity_counts: Record<string, number>;
  recent_alerts: RecentAlert[];
}

export interface GuidanceStats {
  total_issued: number;
  active_count: number;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const dashboardApi = {
  profileStats: () =>
    httpClient.get<ProfileStats>("/api/v1/profiles/stats").then((r) => r.data),

  loanStats: () =>
    httpClient.get<LoanStats>("/api/v1/loans/stats").then((r) => r.data),

  riskStats: () =>
    httpClient.get<RiskStats>("/api/v1/risk/stats").then((r) => r.data),

  alertStats: () =>
    httpClient.get<AlertStats>("/api/v1/early-warning/stats").then((r) => r.data),

  guidanceStats: () =>
    httpClient.get<GuidanceStats>("/api/v1/guidance/stats").then((r) => r.data),
};
