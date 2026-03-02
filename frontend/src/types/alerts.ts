import {
  AlertSeverity,
  AlertStatus,
  AlertType,
  ScenarioType,
  RiskCategory,
} from "./shared";

// ─── Alert Types ────────────────────────────────────────────────────────────

export interface ActionableRecommendation {
  priority: number;
  action: string;
  expected_impact: string;
  timeline: string;
}

export interface RiskFactorSnapshot {
  factor_type: string;
  current_value: number;
  threshold: number;
  severity: AlertSeverity;
  description: string;
}

export interface Alert {
  alert_id: string;
  profile_id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  status: AlertStatus;
  risk_factors: RiskFactorSnapshot[];
  recommendations: ActionableRecommendation[];
  message: string;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

// ─── Scenario Types ────────────────────────────────────────────────────────

export interface ScenarioParameters {
  scenario_type: ScenarioType;
  income_shock_percentage?: number;
  duration_months?: number;
  affected_categories?: string[];
  description?: string;
}

export interface ScenarioProjection {
  month: number;
  year: number;
  baseline_income: number;
  stressed_income: number;
  baseline_expenses: number;
  stressed_expenses: number;
  net_impact: number;
}

export interface CapacityImpact {
  baseline_capacity: number;
  stressed_capacity: number;
  capacity_reduction_pct: number;
  can_service_existing_debt: boolean;
  max_additional_emi: number;
}

export interface ScenarioRecommendation {
  priority: number;
  action: string;
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
  generated_at: string;
}

export interface ComparisonResult {
  comparison_id: string;
  profile_id: string;
  simulations: SimulationResult[];
  summary: string;
  generated_at: string;
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
  scenario: ScenarioParameters;
}
