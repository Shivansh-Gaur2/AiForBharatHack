import { RiskCategory, AlertSeverity, LoanStatus, GuidanceStatus, TimingSuitability } from "@/types";

type ColorMap = Record<string, string>;

export const RISK_COLORS: ColorMap = {
  [RiskCategory.LOW]: "text-green-700 bg-green-100",
  [RiskCategory.MEDIUM]: "text-yellow-700 bg-yellow-100",
  [RiskCategory.HIGH]: "text-orange-700 bg-orange-100",
  [RiskCategory.VERY_HIGH]: "text-red-700 bg-red-100",
};

export const RISK_CHART_COLORS: Record<string, string> = {
  [RiskCategory.LOW]: "#22c55e",
  [RiskCategory.MEDIUM]: "#eab308",
  [RiskCategory.HIGH]: "#f97316",
  [RiskCategory.VERY_HIGH]: "#ef4444",
};

export const ALERT_COLORS: ColorMap = {
  [AlertSeverity.INFO]: "text-blue-700 bg-blue-100 border-blue-300",
  [AlertSeverity.WARNING]: "text-yellow-700 bg-yellow-100 border-yellow-300",
  [AlertSeverity.CRITICAL]: "text-red-700 bg-red-100 border-red-300",
};

export const LOAN_STATUS_COLORS: ColorMap = {
  [LoanStatus.ACTIVE]: "text-blue-700 bg-blue-100",
  [LoanStatus.CLOSED]: "text-gray-700 bg-gray-100",
  [LoanStatus.DEFAULTED]: "text-red-700 bg-red-100",
  [LoanStatus.RESTRUCTURED]: "text-purple-700 bg-purple-100",
};

export const GUIDANCE_STATUS_COLORS: ColorMap = {
  [GuidanceStatus.DRAFT]: "text-gray-700 bg-gray-100",
  [GuidanceStatus.ACTIVE]: "text-green-700 bg-green-100",
  [GuidanceStatus.EXPIRED]: "text-yellow-700 bg-yellow-100",
  [GuidanceStatus.SUPERSEDED]: "text-purple-700 bg-purple-100",
};

export const TIMING_COLORS: ColorMap = {
  [TimingSuitability.OPTIMAL]: "text-green-700 bg-green-100",
  [TimingSuitability.GOOD]: "text-blue-700 bg-blue-100",
  [TimingSuitability.ACCEPTABLE]: "text-yellow-700 bg-yellow-100",
  [TimingSuitability.POOR]: "text-red-700 bg-red-100",
};
