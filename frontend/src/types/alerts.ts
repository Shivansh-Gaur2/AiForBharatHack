import {
  AlertSeverity,
  AlertStatus,
  AlertType,
  ScenarioType,
  RiskCategory,
} from "./shared";

// ─── Alert Types ────────────────────────────────────────────────────────────

export interface ActionableRecommendation {
  priority: number | string;
  action: string;
  rationale: string;
  estimated_impact: string;
}

export interface RiskFactorSnapshot {
  factor_name: string;
  current_value: number;
  threshold: number;
  severity_contribution: string;
}

export interface Alert {
  alert_id: string;
  profile_id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  description: string;
  risk_factors: RiskFactorSnapshot[];
  recommendations: ActionableRecommendation[];
  created_at: string;
  updated_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

// ─── Scenario Types ────────────────────────────────────────────────────────

export interface ScenarioParameters {
  scenario_type: ScenarioType;
  name?: string;
  description?: string;
  income_reduction_pct?: number;
  weather_adjustment?: number;
  market_price_change_pct?: number;
  duration_months?: number;
}

export interface ScenarioProjection {
  month: number;
  year: number;
  baseline_inflow: number;
  stressed_inflow: number;
  baseline_outflow: number;
  stressed_outflow: number;
  baseline_net: number;
  stressed_net: number;
}

export interface CapacityImpact {
  original_recommended_emi: number;
  stressed_recommended_emi: number;
  original_max_emi: number;
  stressed_max_emi: number;
  original_dscr: number;
  stressed_dscr: number;
  emi_reduction_pct: number;
  can_still_repay: boolean;
}

export interface ScenarioRecommendation {
  recommendation: string;
  risk_level: string;
  confidence: string;
  rationale: string;
}

export interface SimulationResult {
  simulation_id: string;
  profile_id: string;
  scenario: ScenarioParameters;
  projections: ScenarioProjection[];
  capacity_impact: CapacityImpact;
  recommendations: ScenarioRecommendation[];
  overall_risk_level: RiskCategory;
  total_income_loss: number;
  months_in_deficit: number;
  created_at: string;
}

export interface ComparisonResult {
  profile_id: string;
  results: SimulationResult[];
  count: number;
}

// ─── API Request DTOs ──────────────────────────────────────────────────────

export interface MonitorRequest {
  profile_id: string;
}

export interface DirectAlertRequest {
  profile_id: string;
  income_deviations: Array<{
    month: number;
    year: number;
    expected: number;
    actual: number;
  }>;
  repayment_stress: Array<{
    tracking_id: string;
    outstanding: number;
    monthly_emi: number;
    months_overdue: number;
  }>;
  total_debt: number;
  monthly_income: number;
}

export interface ScenarioRequest {
  profile_id: string;
  scenario_type: ScenarioType;
  name: string;
  description?: string;
  income_reduction_pct?: number;
  weather_adjustment?: number;
  market_price_change_pct?: number;
  duration_months?: number;
  existing_monthly_obligations?: number;
  household_monthly_expense?: number;
}
