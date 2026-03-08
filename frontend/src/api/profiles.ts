import { httpClient } from "./client";
import type {
  ProfileDetail,
  ProfileSummary,
  CreateProfileRequest,
  UpdatePersonalInfoRequest,
  UpdateLivelihoodRequest,
  AddIncomeRecordsRequest,
  AddExpenseRecordsRequest,
  SetSeasonalFactorsRequest,
  VolatilityMetrics,
  PaginatedResponse,
} from "@/types";

const BASE = "/api/v1/profiles";

export const profileApi = {
  create: (data: CreateProfileRequest) =>
    httpClient.post<ProfileDetail>(BASE, data).then((r) => r.data),

  get: (id: string) =>
    httpClient.get<ProfileDetail>(`${BASE}/${id}`).then((r) => r.data),

  list: (params?: { limit?: number; cursor?: string }) =>
    httpClient
      .get<PaginatedResponse<ProfileSummary>>(BASE, { params })
      .then((r) => r.data),

  updatePersonalInfo: (id: string, data: UpdatePersonalInfoRequest) =>
    httpClient
      .patch<ProfileDetail>(`${BASE}/${id}/personal-info`, data)
      .then((r) => r.data),

  updateLivelihood: (id: string, data: UpdateLivelihoodRequest) =>
    httpClient
      .patch<ProfileDetail>(`${BASE}/${id}/livelihood`, data)
      .then((r) => r.data),

  addIncomeRecords: (id: string, data: AddIncomeRecordsRequest) =>
    httpClient
      .post<ProfileDetail>(`${BASE}/${id}/income`, data)
      .then((r) => r.data),

  addExpenseRecords: (id: string, data: AddExpenseRecordsRequest) =>
    httpClient
      .post<ProfileDetail>(`${BASE}/${id}/expenses`, data)
      .then((r) => r.data),

  setSeasonalFactors: (id: string, data: SetSeasonalFactorsRequest) =>
    httpClient
      .put<ProfileDetail>(`${BASE}/${id}/seasonal-factors`, data)
      .then((r) => r.data),

  getVolatility: (id: string) =>
    httpClient
      .get<VolatilityMetrics>(`${BASE}/${id}/volatility`)
      .then((r) => r.data),

  delete: (id: string) =>
    httpClient.delete(`${BASE}/${id}`).then((r) => r.data),
};
