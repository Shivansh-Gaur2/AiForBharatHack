import { CashFlowCategory, FlowDirection } from "./shared";

// ─── Domain Types ───────────────────────────────────────────────────────────

export interface CashFlowRecord {
  record_id: string;
  profile_id: string;
  month: number;
  year: number;
  amount: number;
  category: CashFlowCategory;
  direction: FlowDirection;
  description: string;
  recorded_at: string;
}

export interface MonthlyProjection {
  month: number;
  year: number;
  projected_inflow: number;
  projected_outflow: number;
  net_cash_flow: number;
  confidence: string;
}

export interface SeasonalPattern {
  season: string;
  avg_inflow: number;
  avg_outflow: number;
  net_flow: number;
  months: number[];
}

export interface UncertaintyBand {
  month: number;
  year: number;
  lower_bound: number;
  upper_bound: number;
  confidence_level: number;
}

export interface TimingWindow {
  start_month: number;
  start_year: number;
  end_month: number;
  end_year: number;
  suitability: string;
  expected_surplus: number;
  reason: string;
}

export interface RepaymentCapacity {
  profile_id: string;
  monthly_disposable_income: number;
  max_emi_affordable: number;
  recommended_emi: number;
  safety_margin: number;
  assessed_at: string;
}

// ─── API DTOs ───────────────────────────────────────────────────────────────

export interface CashFlowForecast {
  forecast_id: string;
  profile_id: string;
  monthly_projections: MonthlyProjection[];
  seasonal_patterns: SeasonalPattern[];
  uncertainty_bands: UncertaintyBand[];
  assumptions: string[];
  repayment_capacity: RepaymentCapacity | null;
  timing_windows: TimingWindow[];
  model_version: string;
  generated_at: string;
}

export interface RecordCashFlowRequest {
  profile_id: string;
  month: number;
  year: number;
  amount: number;
  category: CashFlowCategory;
  direction: FlowDirection;
  description?: string;
}

export interface GenerateForecastRequest {
  profile_id: string;
  horizon_months?: number;
}
