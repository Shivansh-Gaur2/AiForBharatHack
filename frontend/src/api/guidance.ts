import { httpClient } from "./client";
import type {
  CreditGuidance,
  GuidanceExplanation,
  GuidanceRequest,
} from "@/types";

const BASE = "/api/v1/guidance";

export const guidanceApi = {
  generate: (data: GuidanceRequest) =>
    httpClient
      .post<CreditGuidance>(`${BASE}/generate`, data)
      .then((r) => r.data),

  get: (guidanceId: string) =>
    httpClient.get<CreditGuidance>(`${BASE}/${guidanceId}`).then((r) => r.data),

  explain: (guidanceId: string) =>
    httpClient
      .get<GuidanceExplanation>(`${BASE}/${guidanceId}/explain`)
      .then((r) => r.data),

  getHistory: (profileId: string, limit?: number) =>
    httpClient
      .get<{ items: CreditGuidance[] }>(
        `${BASE}/profile/${profileId}/history`,
        {
          params: limit ? { limit } : undefined,
        },
      )
      .then((r) => r.data),

  getActive: (profileId: string) =>
    httpClient
      .get<{ items: CreditGuidance[] }>(
        `${BASE}/profile/${profileId}/active`,
      )
      .then((r) => r.data),

  supersede: (guidanceId: string) =>
    httpClient
      .post<CreditGuidance>(`${BASE}/${guidanceId}/supersede`)
      .then((r) => r.data),

  expire: (guidanceId: string) =>
    httpClient
      .post<CreditGuidance>(`${BASE}/${guidanceId}/expire`)
      .then((r) => r.data),
};
