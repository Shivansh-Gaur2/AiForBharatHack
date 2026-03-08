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
  category: string;
  direction: string;
  season: string;
  months: number[];
  average_monthly_amount: number;
  peak_month: number;
  variability_cv: number;
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
  suitability_score: number;
  reason: string;
}

export interface RepaymentCapacity {
  profile_id: string;
  monthly_surplus_avg: number;
  monthly_surplus_min: number;
  max_affordable_emi: number;
  recommended_emi: number;
  emergency_reserve: number;
  annual_repayment_capacity: number;
  debt_service_coverage_ratio: number;
  computed_at: string;
}

// ─── API DTOs ───────────────────────────────────────────────────────────────

export interface ForecastAssumption {
  factor: string;
  description: string;
  impact: string;
}

export interface CashFlowForecast {
  forecast_id: string;
  profile_id: string;
  forecast_period_start_month: number;
  forecast_period_start_year: number;
  forecast_period_end_month: number;
  forecast_period_end_year: number;
  monthly_projections: MonthlyProjection[];
  seasonal_patterns: SeasonalPattern[];
  uncertainty_bands: UncertaintyBand[];
  assumptions: ForecastAssumption[];
  repayment_capacity: RepaymentCapacity | null;
  timing_windows: TimingWindow[];
  best_timing_window: TimingWindow | null;
  total_projected_inflow: number;
  total_projected_outflow: number;
  model_version: string;
  created_at: string;
  updated_at: string;
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
