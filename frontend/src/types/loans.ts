import { LoanSourceType, LoanStatus } from "./shared";

// ─── Domain Types ───────────────────────────────────────────────────────────

export interface LoanTerms {
  principal: number;
  interest_rate_annual: number;
  tenure_months: number;
  emi_amount: number;
  collateral_description?: string | null;
}

export interface RepaymentRecord {
  date: string;
  amount: number;
  is_late: boolean;
  days_overdue: number;
}

export interface SourceExposure {
  source_type: LoanSourceType;
  total_outstanding: number;
  loan_count: number;
  monthly_obligation: number;
}

// ─── API DTOs ───────────────────────────────────────────────────────────────

export interface LoanDetail {
  tracking_id: string;
  profile_id: string;
  lender_name: string;
  source_type: LoanSourceType;
  terms: LoanTerms;
  status: LoanStatus;
  disbursement_date: string;
  maturity_date: string | null;
  outstanding_balance: number;
  total_repaid: number;
  repayment_rate: number;
  on_time_ratio: number;
  monthly_obligation: number;
  repayment_count: number;
  repayments: RepaymentRecord[];
  purpose: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface LoanSummary {
  tracking_id: string;
  lender_name: string;
  source_type: LoanSourceType;
  principal: number;
  outstanding_balance: number;
  status: LoanStatus;
  monthly_obligation: number;
}

export interface DebtExposure {
  profile_id: string;
  total_outstanding: number;
  monthly_obligations: number;
  debt_to_income_ratio: number;
  credit_utilisation: number;
  by_source: SourceExposure[];
  assessed_at: string;
}

export interface TrackLoanRequest {
  profile_id: string;
  lender_name: string;
  source_type: LoanSourceType;
  terms: {
    principal: number;
    interest_rate_annual: number;
    tenure_months: number;
    emi_amount?: number;
    collateral_description?: string;
  };
  disbursement_date: string;
  maturity_date?: string;
  purpose?: string;
  notes?: string;
}

export interface RecordRepaymentRequest {
  date: string;
  amount: number;
  is_late?: boolean;
  days_overdue?: number;
}

export interface UpdateLoanStatusRequest {
  status: LoanStatus;
}
