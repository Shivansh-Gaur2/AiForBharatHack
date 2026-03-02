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
  recommended_tenure_months: number;
  max_emi: number;
  recommended_emi: number;
  interest_rate_guidance: string;
}

export interface RiskSummary {
  risk_score: number;
  risk_category: RiskCategory;
  key_risks: string[];
}

export interface AlternativeOption {
  description: string;
  amount_range: AmountRange;
  timing: string;
  pros: string[];
  cons: string[];
}

export interface ReasoningStep {
  step: number;
  factor: string;
  analysis: string;
  impact: string;
}

export interface GuidanceExplanation {
  guidance_id: string;
  summary: string;
  reasoning_steps: ReasoningStep[];
  key_assumptions: string[];
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
  valid_until: string;
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
