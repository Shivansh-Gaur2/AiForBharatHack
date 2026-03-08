import { httpClient } from "./client";
import type {
  LoanDetail,
  LoanSummary,
  DebtExposure,
  TrackLoanRequest,
  RecordRepaymentRequest,
  UpdateLoanStatusRequest,
  PaginatedResponse,
} from "@/types";

const BASE = "/api/v1/loans";

export const loanApi = {
  track: (data: TrackLoanRequest) =>
    httpClient.post<LoanDetail>(BASE, data).then((r) => r.data),

  get: (trackingId: string) =>
    httpClient.get<LoanDetail>(`${BASE}/${trackingId}`).then((r) => r.data),

  recordRepayment: (trackingId: string, data: RecordRepaymentRequest) =>
    httpClient
      .post<LoanDetail>(`${BASE}/${trackingId}/repayments`, data)
      .then((r) => r.data),

  updateStatus: (trackingId: string, data: UpdateLoanStatusRequest) =>
    httpClient
      .patch<LoanDetail>(`${BASE}/${trackingId}/status`, data)
      .then((r) => r.data),

  listByBorrower: (
    profileId: string,
    params?: { active_only?: boolean; limit?: number; cursor?: string },
  ) =>
    httpClient
      .get<PaginatedResponse<LoanSummary>>(`${BASE}/borrower/${profileId}`, {
        params,
      })
      .then((r) => r.data),

  getExposure: (profileId: string, annualIncome?: number) =>
    httpClient
      .get<DebtExposure>(`${BASE}/borrower/${profileId}/exposure`, {
        params: annualIncome ? { annual_income: annualIncome } : undefined,
      })
      .then((r) => r.data),
};
