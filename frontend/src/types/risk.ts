import { RiskCategory } from "./shared";

// ─── Domain Types ───────────────────────────────────────────────────────────

export interface RiskFactor {
  factor_type: string;
  score: number;
  weight: number;
  weighted_score: number;
  description: string;
}

export interface RiskExplanation {
  summary: string;
  key_factors: string[];
  recommendations: string[];
}

// ─── API DTOs ───────────────────────────────────────────────────────────────

export interface RiskAssessment {
  assessment_id: string;
  profile_id: string;
  risk_score: number;
  risk_category: RiskCategory;
  confidence_level: number;
  factors: RiskFactor[];
  explanation: RiskExplanation;
  valid_until: string;
  model_version: string;
  assessed_at: string;
}

export interface RiskSummary {
  assessment_id: string;
  risk_score: number;
  risk_category: RiskCategory;
  assessed_at: string;
}

export interface AssessRiskRequest {
  profile_id: string;
}

export interface DirectRiskInput {
  profile_id: string;
  income_volatility: number;
  debt_to_income_ratio: number;
  repayment_history_score: number;
  seasonal_risk_score: number;
  weather_risk_score: number;
  market_risk_score: number;
  demographic_score: number;
  crop_diversification_score: number;
  total_outstanding_debt: number;
  monthly_income: number;
  monthly_expenses: number;
  number_of_active_loans: number;
  years_of_credit_history: number;
  has_crop_insurance: boolean;
  irrigation_percentage: number;
  distance_to_market_km: number;
}

export interface RiskExplainDTO {
  assessment_id: string;
  risk_score: number;
  risk_category: RiskCategory;
  summary: string;
  key_factors: string[];
  recommendations: string[];
}
