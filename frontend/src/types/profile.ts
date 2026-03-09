import { OccupationType, Season } from "./shared";

// ─── Domain Types ───────────────────────────────────────────────────────────

export interface PersonalInfo {
  name: string;
  age: number;
  gender: string;
  location: string;
  district: string;
  state: string;
  phone?: string;
  aadhaar_last_four?: string;
}

export interface LandDetails {
  owned_acres: number;
  leased_acres: number;
  irrigated_percentage: number;
}

export interface CropInfo {
  crop_name: string;
  season: Season;
  area_acres: number;
  expected_yield_quintals: number;
  expected_price_per_quintal: number;
}

export interface LivestockInfo {
  animal_type: string;
  count: number;
  monthly_income: number;
  monthly_expense: number;
}

export interface MigrationInfo {
  destination: string;
  duration_months: number;
  monthly_income: number;
  season: Season;
}

export interface BusinessDetails {
  business_type: string;
  workspace_owned: boolean;
  workspace_description: string;
  monthly_revenue: number;
  monthly_expenses: number;
  investment_amount: number;
  years_in_business: number;
}

export interface LivelihoodInfo {
  primary_occupation: OccupationType;
  secondary_occupations: OccupationType[];
  land_details?: LandDetails;
  crops: CropInfo[];
  livestock: LivestockInfo[];
  migration_patterns: MigrationInfo[];
  business_details?: BusinessDetails;
}

export interface IncomeRecord {
  month: number;
  year: number;
  amount: number;
  source: string;
  category: string;
  is_recurring: boolean;
}

export interface ExpenseRecord {
  month: number;
  year: number;
  amount: number;
  category: string;
  is_recurring: boolean;
}

export interface SeasonalFactor {
  season: Season;
  income_multiplier: number;
  expense_multiplier: number;
  description: string;
}

export interface VolatilityMetrics {
  coefficient_of_variation: number;
  income_range_ratio: number;
  seasonal_variance: number;
  months_below_average: number;
  volatility_level: "LOW" | "MEDIUM" | "HIGH";
}

// ─── API DTOs ───────────────────────────────────────────────────────────────

export interface ProfileDetail {
  profile_id: string;
  personal_info: PersonalInfo;
  livelihood_info: LivelihoodInfo;
  income_records: IncomeRecord[];
  expense_records: ExpenseRecord[];
  seasonal_factors: SeasonalFactor[];
  volatility_metrics: VolatilityMetrics | null;
  average_monthly_income: number;
  average_monthly_expense: number;
  monthly_surplus: number;
  estimated_annual_income: number;
  created_at: string;
  updated_at: string;
}

export interface ProfileSummary {
  profile_id: string;
  name: string;
  occupation: OccupationType;
  location: string;
  volatility_level: string | null;
  created_at: string;
}

export interface CreateProfileRequest {
  personal_info: PersonalInfo;
  livelihood_info: LivelihoodInfo;
  income_records?: IncomeRecord[];
  expense_records?: ExpenseRecord[];
  seasonal_factors?: SeasonalFactor[];
}

export interface UpdatePersonalInfoRequest {
  personal_info: Partial<PersonalInfo>;
}

export interface UpdateLivelihoodRequest {
  livelihood_info: Partial<LivelihoodInfo>;
}

export interface AddIncomeRecordsRequest {
  records: IncomeRecord[];
}

export interface AddExpenseRecordsRequest {
  records: ExpenseRecord[];
}

export interface SetSeasonalFactorsRequest {
  factors: SeasonalFactor[];
}
