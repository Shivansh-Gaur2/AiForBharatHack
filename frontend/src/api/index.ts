export { httpClient, ApiError } from "./client";
export { authApi } from "./auth";
export type { AuthUser, AuthResponse, LoginRequest, RegisterRequest } from "./auth";
export { dashboardApi } from "./dashboard";
export { securityApi } from "./security";
export type {
  ConsentRecord,
  ConsentListResponse,
  AuditEntry,
  AuditLogResponse,
  RetentionPolicy,
  RetentionPolicyListResponse,
  GrantConsentPayload,
} from "./security";
export type {
  ProfileStats,
  LoanStats,
  RiskStats,
  AlertStats,
  GuidanceStats,
  RecentAlert,
} from "./dashboard";
export { profileApi } from "./profiles";
export { loanApi } from "./loans";
export { riskApi } from "./risk";
export { cashflowApi } from "./cashflow";
export { alertApi } from "./alerts";
export { guidanceApi } from "./guidance";
