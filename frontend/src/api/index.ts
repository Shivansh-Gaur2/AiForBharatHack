export { httpClient, ApiError } from "./client";
export { authApi } from "./auth";
export type { AuthUser, AuthResponse, LoginRequest, RegisterRequest } from "./auth";
export { dashboardApi } from "./dashboard";
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
export { securityApi } from "./security";
export type {
  ConsentDTO,
  ConsentListDTO,
  AuditEntryDTO,
  AuditLogDTO,
  LineageRecordDTO,
  DataUsageSummaryDTO,
  RetentionPolicyDTO,
  SecurityStats,
} from "./security";
export { aiAdvisorApi } from "./advisor";
export type {
  ConversationResponse,
  ConversationDetail,
  ConversationListItem,
  MessageDTO,
  QuickAnalysisResponse,
  ScenarioAnalysisResponse,
} from "./advisor";
