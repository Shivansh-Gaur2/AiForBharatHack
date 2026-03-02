import { httpClient } from "./client";
import type {
  CashFlowForecast,
  CashFlowRecord,
  RepaymentCapacity,
  TimingWindow,
  RecordCashFlowRequest,
  GenerateForecastRequest,
} from "@/types";

const BASE = "/api/v1/cashflow";

export const cashflowApi = {
  recordCashFlow: (data: RecordCashFlowRequest) =>
    httpClient
      .post<CashFlowRecord>(`${BASE}/records`, data)
      .then((r) => r.data),

  getRecords: (profileId: string, limit?: number) =>
    httpClient
      .get<{ records: CashFlowRecord[] }>(`${BASE}/records/${profileId}`, {
        params: limit ? { limit } : undefined,
      })
      .then((r) => r.data),

  generateForecast: (data: GenerateForecastRequest) =>
    httpClient
      .post<CashFlowForecast>(`${BASE}/forecast`, data)
      .then((r) => r.data),

  getForecast: (forecastId: string) =>
    httpClient
      .get<CashFlowForecast>(`${BASE}/forecast/${forecastId}`)
      .then((r) => r.data),

  getLatestForecast: (profileId: string) =>
    httpClient
      .get<CashFlowForecast>(`${BASE}/forecast/profile/${profileId}`)
      .then((r) => r.data),

  getCapacity: (profileId: string) =>
    httpClient
      .get<RepaymentCapacity>(`${BASE}/capacity/${profileId}`)
      .then((r) => r.data),

  getTimingWindows: (profileId: string) =>
    httpClient
      .get<TimingWindow[]>(`${BASE}/timing/${profileId}`)
      .then((r) => r.data),
};
