import {
  GuidanceStatus,
  LoanPurpose,
  RiskCategory,
  TimingSuitability,
  AmountRange,
} from "./shared";

// ─── Domain Types ───────────────────────────────────────────────────────────

export interface GuidanceTimingWindow {
  start_month: number;
  start_year: number;
  end_month: number;
  end_year: number;
  suitability: TimingSuitability;
  expected_surplus: number;
  reason: string;
}

export interface SuggestedTerms {
  tenure_months: number;
  interest_rate_max_pct: number;
  emi_amount: number;
  total_repayment: number;
  source_recommendation: string;
}

export interface RiskSummary {
  risk_score: number;
  risk_category: RiskCategory;
  dti_ratio: number;
  repayment_capacity_pct: number;
  key_risk_factors: string[];
}

export interface AlternativeOption {
  option_type: string;
  description: string;
  estimated_amount: number;
  timing: string;
  advantages: string[];
  disadvantages: string[];
}

export interface ReasoningStep {
  step_number: number;
  factor: string;
  observation: string;
  impact: string;
}

export interface GuidanceExplanation {
  summary: string;
  reasoning_steps: ReasoningStep[];
  confidence: string;
  caveats: string[];
}

// ─── API DTOs ───────────────────────────────────────────────────────────────

export interface CreditGuidance {
  guidance_id: string;
  profile_id: string;
  loan_purpose: LoanPurpose;
  requested_amount: number;
  recommended_amount: AmountRange;
  optimal_timing: GuidanceTimingWindow | null;
  suggested_terms: SuggestedTerms | null;
  risk_summary: RiskSummary | null;
  alternative_options: AlternativeOption[];
  explanation: GuidanceExplanation | null;
  status: GuidanceStatus;
  created_at: string;
  expires_at: string | null;
}

export interface GuidanceRequest {
  profile_id: string;
  loan_purpose: LoanPurpose;
  requested_amount: number;
}

export interface TimingRequest {
  profile_id: string;
  loan_amount: number;
}

export interface AmountRequest {
  profile_id: string;
  loan_purpose: LoanPurpose;
}
