import { httpClient } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ConsentRecord {
  consent_id: string;
  profile_id: string;
  purpose: string;
  status: "ACTIVE" | "REVOKED" | "EXPIRED";
  granted_at: string;
  expires_at: string;
  revoked_at: string | null;
  granted_by: string;
  revocation_reason: string;
  version: number;
}

export interface ConsentListResponse {
  items: ConsentRecord[];
  count: number;
}

export interface AuditEntry {
  entry_id: string;
  timestamp: string;
  actor_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  profile_id: string;
  details: Record<string, unknown>;
  success: boolean;
}

export interface AuditLogResponse {
  items: AuditEntry[];
  count: number;
}

export interface RetentionPolicy {
  policy_id: string;
  data_category: string;
  retention_days: number;
  action: string;
  description: string;
  is_active: boolean;
}

export interface RetentionPolicyListResponse {
  items: RetentionPolicy[];
  count: number;
}

export interface GrantConsentPayload {
  profile_id: string;
  purpose: string;
  granted_by?: string;
  duration_days?: number;
}

export interface RevokeConsentPayload {
  reason?: string;
  revoked_by?: string;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

const BASE = "/api/v1/security";

export const securityApi = {
  /** Grant consent for a data-use purpose */
  grantConsent: (payload: GrantConsentPayload) =>
    httpClient
      .post<ConsentRecord>(`${BASE}/consent`, {
        profile_id: payload.profile_id,
        purpose: payload.purpose,
        granted_by: payload.granted_by ?? "",
        duration_days: payload.duration_days ?? 365,
      })
      .then((r) => r.data),

  /** Get all consents for a profile */
  getProfileConsents: (profileId: string) =>
    httpClient
      .get<ConsentListResponse>(`${BASE}/consent/profile/${profileId}`)
      .then((r) => r.data),

  /** Revoke a consent */
  revokeConsent: (consentId: string, payload?: RevokeConsentPayload) =>
    httpClient
      .post<ConsentRecord>(`${BASE}/consent/${consentId}/revoke`, {
        reason: payload?.reason ?? "",
        revoked_by: payload?.revoked_by ?? "",
      })
      .then((r) => r.data),

  /** Get audit log entries for a profile */
  getAuditLog: (profileId: string, limit = 50) =>
    httpClient
      .get<AuditLogResponse>(`${BASE}/audit/profile/${profileId}`, {
        params: { limit },
      })
      .then((r) => r.data),

  /** Get retention policies */
  getRetentionPolicies: () =>
    httpClient
      .get<RetentionPolicyListResponse>(`${BASE}/retention/policies`)
      .then((r) => r.data),

  /** Initialize default retention policies (idempotent) */
  initRetentionPolicies: () =>
    httpClient
      .post<RetentionPolicyListResponse>(`${BASE}/retention/initialize`, {})
      .then((r) => r.data),
};
