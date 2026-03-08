import { httpClient } from "./client";
import type {
  Alert,
  SimulationResult,
  ComparisonResult,
  MonitorRequest,
  ScenarioRequest,
  ScenarioParameters,
} from "@/types";

const BASE = "/api/v1/early-warning";

export const alertApi = {
  monitor: (data: MonitorRequest) =>
    httpClient.post<Alert>(`${BASE}/monitor`, data).then((r) => r.data),

  getAlert: (alertId: string) =>
    httpClient.get<Alert>(`${BASE}/alerts/${alertId}`).then((r) => r.data),

  listByProfile: (profileId: string, limit?: number) =>
    httpClient
      .get<{ items: Alert[]; count: number }>(`${BASE}/alerts/profile/${profileId}`, {
        params: limit ? { limit } : undefined,
      })
      .then((r) => r.data),

  getActiveAlerts: (profileId: string) =>
    httpClient
      .get<{ items: Alert[]; count: number }>(`${BASE}/alerts/profile/${profileId}/active`)
      .then((r) => r.data),

  escalate: (alertId: string, severity: string) =>
    httpClient
      .post<Alert>(`${BASE}/alerts/${alertId}/escalate`, {
        new_severity: severity,
      })
      .then((r) => r.data),

  acknowledge: (alertId: string) =>
    httpClient
      .post<Alert>(`${BASE}/alerts/${alertId}/acknowledge`)
      .then((r) => r.data),

  resolve: (alertId: string) =>
    httpClient
      .post<Alert>(`${BASE}/alerts/${alertId}/resolve`)
      .then((r) => r.data),

  simulate: (data: ScenarioRequest) =>
    httpClient
      .post<SimulationResult>(`${BASE}/scenarios/simulate`, data)
      .then((r) => r.data),

  compare: (profileId: string, scenarios: ScenarioParameters[]) =>
    httpClient
      .post<ComparisonResult>(`${BASE}/scenarios/compare`, {
        profile_id: profileId,
        scenarios: scenarios.map((s) => ({
          ...s,
          name: s.name ?? `${s.scenario_type} scenario`,
        })),
      })
      .then((r) => r.data),

  getSimulation: (simulationId: string) =>
    httpClient
      .get<SimulationResult>(`${BASE}/scenarios/${simulationId}`)
      .then((r) => r.data),
};
