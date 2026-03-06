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
  repayment_date: string;
  amount: number;
  principal_component: number;
  interest_component: number;
  penalty: number;
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
  maturity_date: string;
  outstanding_balance: number;
  total_repaid: number;
  repayments: RepaymentRecord[];
  created_at: string;
  updated_at: string;
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
  amount: number;
  principal_component: number;
  interest_component: number;
  penalty?: number;
  repayment_date?: string;
}

export interface UpdateLoanStatusRequest {
  status: LoanStatus;
  reason?: string;
}
