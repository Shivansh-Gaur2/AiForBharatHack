import { httpClient } from "./client";
import type {
  RiskAssessment,
  RiskSummary,
  AssessRiskRequest,
  RiskExplainDTO,
} from "@/types";

const BASE = "/api/v1/risk";

export const riskApi = {
  assess: (data: AssessRiskRequest) =>
    httpClient.post<RiskAssessment>(`${BASE}/assess`, data).then((r) => r.data),

  getByProfile: (profileId: string) =>
    httpClient
      .get<RiskAssessment>(`${BASE}/profile/${profileId}`)
      .then((r) => r.data),

  getHistory: (profileId: string, limit?: number) =>
    httpClient
      .get<RiskSummary[]>(`${BASE}/profile/${profileId}/history`, {
        params: limit ? { limit } : undefined,
      })
      .then((r) => r.data),

  get: (assessmentId: string) =>
    httpClient
      .get<RiskAssessment>(`${BASE}/${assessmentId}`)
      .then((r) => r.data),

  explain: (assessmentId: string) =>
    httpClient
      .get<RiskExplainDTO>(`${BASE}/${assessmentId}/explain`)
      .then((r) => r.data),
};
