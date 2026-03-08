import { httpClient } from "./client";

const BASE = "/api/v1/security";

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface GrantConsentRequest {
  profile_id: string;
  purpose: string;
  granted_by?: string;
  duration_days?: number;
}

export interface RevokeConsentRequest {
  reason?: string;
  revoked_by?: string;
}

export interface DataAccessRequest {
  actor_id: string;
  resource_type: string;
  resource_id: string;
  profile_id: string;
  details?: Record<string, unknown>;
  ip_address?: string;
}

export interface LineageRequest {
  profile_id: string;
  data_category: string;
  source_service: string;
  target_service: string;
  action: string;
  fields_accessed?: string[];
  purpose?: string;
  consent_id?: string;
  actor_id?: string;
}

export interface ConsentCheckRequest {
  profile_id: string;
  purpose: string;
}

export interface RetentionCheckRequest {
  profile_id: string;
  data_category: string;
  data_created_at: string;
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface ConsentDTO {
  consent_id: string;
  profile_id: string;
  purpose: string;
  status: string;
  granted_at: string;
  expires_at: string;
  revoked_at: string | null;
  granted_by: string;
  revocation_reason: string;
  version: number;
}

export interface ConsentListDTO {
  items: ConsentDTO[];
  count: number;
}

export interface ConsentCheckDTO {
  profile_id: string;
  purpose: string;
  has_consent: boolean;
}

export interface AuditEntryDTO {
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

export interface AuditLogDTO {
  items: AuditEntryDTO[];
  count: number;
}

export interface LineageRecordDTO {
  record_id: string;
  timestamp: string;
  profile_id: string;
  data_category: string;
  source_service: string;
  target_service: string;
  action: string;
  fields_accessed: string[];
  purpose: string;
  consent_id: string;
}

export interface LineageListDTO {
  items: LineageRecordDTO[];
  count: number;
}

export interface RetentionPolicyDTO {
  policy_id: string;
  data_category: string;
  retention_days: number;
  action: string;
  description: string;
  is_active: boolean;
}

export interface RetentionPolicyListDTO {
  items: RetentionPolicyDTO[];
  count: number;
}

export interface RetentionCheckDTO {
  expired: boolean;
  data_category: string;
  retention_days: number;
  action: string;
  reason: string;
}

export interface DataUsageSummaryDTO {
  profile_id: string;
  active_consent_count: number;
  active_consents: ConsentDTO[];
  total_data_accesses: number;
  services_with_access: string[];
  data_categories_stored: string[];
  last_accessed_at: string | null;
  pending_deletion_categories: string[];
  retention_policies: RetentionPolicyDTO[];
}

export interface SecurityStats {
  total_consents: number;
  active_consents: number;
  total_audit_entries: number;
  total_lineage_records: number;
  retention_policies_active: number;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const securityApi = {
  // --- Consent Management ---
  grantConsent: (data: GrantConsentRequest) =>
    httpClient.post<ConsentDTO>(`${BASE}/consent`, data).then((r) => r.data),

  revokeConsent: (consentId: string, data: RevokeConsentRequest = {}) =>
    httpClient
      .post<ConsentDTO>(`${BASE}/consent/${consentId}/revoke`, data)
      .then((r) => r.data),

  getConsent: (consentId: string) =>
    httpClient
      .get<ConsentDTO>(`${BASE}/consent/${consentId}`)
      .then((r) => r.data),

  getProfileConsents: (profileId: string) =>
    httpClient
      .get<ConsentListDTO>(`${BASE}/consent/profile/${profileId}`)
      .then((r) => r.data),

  checkConsent: (data: ConsentCheckRequest) =>
    httpClient
      .post<ConsentCheckDTO>(`${BASE}/consent/check`, data)
      .then((r) => r.data),

  // --- Audit Log ---
  logAccess: (data: DataAccessRequest) =>
    httpClient
      .post<AuditEntryDTO>(`${BASE}/audit/access`, data)
      .then((r) => r.data),

  getAuditLog: (profileId: string, limit = 50) =>
    httpClient
      .get<AuditLogDTO>(`${BASE}/audit/profile/${profileId}`, {
        params: { limit },
      })
      .then((r) => r.data),

  // --- Data Lineage ---
  recordLineage: (data: LineageRequest) =>
    httpClient
      .post<LineageRecordDTO>(`${BASE}/lineage`, data)
      .then((r) => r.data),

  getLineage: (profileId: string, category?: string) =>
    httpClient
      .get<LineageListDTO>(`${BASE}/lineage/profile/${profileId}`, {
        params: category ? { category } : undefined,
      })
      .then((r) => r.data),

  // --- Data Usage ---
  getDataUsage: (profileId: string) =>
    httpClient
      .get<DataUsageSummaryDTO>(`${BASE}/usage/${profileId}`)
      .then((r) => r.data),

  // --- Retention Policies ---
  getRetentionPolicies: () =>
    httpClient
      .get<RetentionPolicyListDTO>(`${BASE}/retention/policies`)
      .then((r) => r.data),

  checkRetention: (data: RetentionCheckRequest) =>
    httpClient
      .post<RetentionCheckDTO>(`${BASE}/retention/check`, data)
      .then((r) => r.data),

  initializeRetentionPolicies: () =>
    httpClient
      .post<RetentionPolicyListDTO>(`${BASE}/retention/initialize`)
      .then((r) => r.data),

  // --- Stats (for dashboard) ---
  stats: () =>
    httpClient
      .get<SecurityStats>(`${BASE}/stats`)
      .then((r) => r.data),
};
