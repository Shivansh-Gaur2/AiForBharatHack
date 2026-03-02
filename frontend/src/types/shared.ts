// ─── Shared Enums ───────────────────────────────────────────────────────────

export enum OccupationType {
  FARMER = "FARMER",
  TENANT_FARMER = "TENANT_FARMER",
  AGRICULTURAL_LABORER = "AGRICULTURAL_LABORER",
  SHG_MEMBER = "SHG_MEMBER",
  SEASONAL_MIGRANT = "SEASONAL_MIGRANT",
  LIVESTOCK_REARER = "LIVESTOCK_REARER",
  ARTISAN = "ARTISAN",
  SMALL_TRADER = "SMALL_TRADER",
  OTHER = "OTHER",
}

export enum LoanSourceType {
  FORMAL = "FORMAL",
  SEMI_FORMAL = "SEMI_FORMAL",
  INFORMAL = "INFORMAL",
}

export enum LoanStatus {
  ACTIVE = "ACTIVE",
  CLOSED = "CLOSED",
  DEFAULTED = "DEFAULTED",
  RESTRUCTURED = "RESTRUCTURED",
}

export enum RiskCategory {
  LOW = "LOW",
  MEDIUM = "MEDIUM",
  HIGH = "HIGH",
  VERY_HIGH = "VERY_HIGH",
}

export enum AlertSeverity {
  INFO = "INFO",
  WARNING = "WARNING",
  CRITICAL = "CRITICAL",
}

export enum AlertType {
  INCOME_DEVIATION = "INCOME_DEVIATION",
  REPAYMENT_STRESS = "REPAYMENT_STRESS",
  OVER_INDEBTEDNESS = "OVER_INDEBTEDNESS",
  WEATHER_RISK = "WEATHER_RISK",
  MARKET_RISK = "MARKET_RISK",
}

export enum AlertStatus {
  ACTIVE = "ACTIVE",
  ACKNOWLEDGED = "ACKNOWLEDGED",
  RESOLVED = "RESOLVED",
  EXPIRED = "EXPIRED",
}

export enum Season {
  KHARIF = "KHARIF",
  RABI = "RABI",
  ZAID = "ZAID",
}

export enum LoanPurpose {
  CROP_CULTIVATION = "CROP_CULTIVATION",
  LIVESTOCK_PURCHASE = "LIVESTOCK_PURCHASE",
  EQUIPMENT_PURCHASE = "EQUIPMENT_PURCHASE",
  LAND_IMPROVEMENT = "LAND_IMPROVEMENT",
  IRRIGATION = "IRRIGATION",
  WORKING_CAPITAL = "WORKING_CAPITAL",
  HOUSING = "HOUSING",
  EDUCATION = "EDUCATION",
  HEALTHCARE = "HEALTHCARE",
  CONSUMPTION = "CONSUMPTION",
  DEBT_CONSOLIDATION = "DEBT_CONSOLIDATION",
  OTHER = "OTHER",
}

export enum GuidanceStatus {
  DRAFT = "DRAFT",
  ACTIVE = "ACTIVE",
  EXPIRED = "EXPIRED",
  SUPERSEDED = "SUPERSEDED",
}

export enum TimingSuitability {
  OPTIMAL = "OPTIMAL",
  GOOD = "GOOD",
  ACCEPTABLE = "ACCEPTABLE",
  POOR = "POOR",
}

export enum ScenarioType {
  INCOME_SHOCK = "INCOME_SHOCK",
  WEATHER_IMPACT = "WEATHER_IMPACT",
  MARKET_VOLATILITY = "MARKET_VOLATILITY",
  COMBINED = "COMBINED",
}

export enum CashFlowCategory {
  CROP_INCOME = "CROP_INCOME",
  LIVESTOCK_INCOME = "LIVESTOCK_INCOME",
  LABOUR_INCOME = "LABOUR_INCOME",
  REMITTANCE = "REMITTANCE",
  GOVERNMENT_SUBSIDY = "GOVERNMENT_SUBSIDY",
  OTHER_INCOME = "OTHER_INCOME",
  SEED_FERTILIZER = "SEED_FERTILIZER",
  LABOUR_EXPENSE = "LABOUR_EXPENSE",
  EQUIPMENT = "EQUIPMENT",
  HOUSEHOLD = "HOUSEHOLD",
  EDUCATION = "EDUCATION",
  HEALTHCARE = "HEALTHCARE",
  LOAN_REPAYMENT = "LOAN_REPAYMENT",
  OTHER_EXPENSE = "OTHER_EXPENSE",
}

export enum FlowDirection {
  INFLOW = "INFLOW",
  OUTFLOW = "OUTFLOW",
}

// ─── Shared Value Objects ───────────────────────────────────────────────────

export interface AmountRange {
  min_amount: number;
  max_amount: number;
  currency: string;
}

export interface DateRange {
  start: string;
  end: string;
}

export interface MonthlyAmount {
  month: number;
  year: number;
  amount: number;
  currency: string;
}

// ─── Pagination ─────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  cursor: string | null;
  has_more: boolean;
}
