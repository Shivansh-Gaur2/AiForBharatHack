import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Lightbulb,
  Clock,
  IndianRupee,
  ShieldCheck,
  CalendarCheck,
  User,
} from "lucide-react";
import { guidanceApi, profileApi } from "@/api";
import {
  Button,
  Card,
  CardTitle,
  Input,
  Select,
  Badge,
  StatCard,
  PageSpinner,
  AlertBanner,
  EmptyState,
} from "@/components/ui";
import {
  formatCurrency,
  formatEnum,
  formatDate,
  getMonthName,
  cn,
} from "@/lib/utils";
import { GUIDANCE_STATUS_COLORS, TIMING_COLORS } from "@/lib/colors";
import { LoanPurpose } from "@/types";
import type { CreditGuidance, GuidanceRequest } from "@/types";

const PURPOSE_OPTIONS = Object.values(LoanPurpose).map((v) => ({
  value: v,
  label: formatEnum(v),
}));

export function GuidancePage() {
  const [activeProfileId, setActiveProfileId] = useState("");
  const [selectedGuidance, setSelectedGuidance] =
    useState<CreditGuidance | null>(null);
  const queryClient = useQueryClient();

  // Form state for generation
  const [purpose, setPurpose] = useState<LoanPurpose>(
    LoanPurpose.CROP_CULTIVATION,
  );
  const [amount, setAmount] = useState("50000");

  // Fetch all profiles for the dropdown
  const { data: profilesData, isLoading: loadingProfiles } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => profileApi.list({ limit: 200 }),
  });

  const profiles = profilesData?.items ?? [];
  const selectedProfile = profiles.find((p) => p.profile_id === activeProfileId);

  // Active guidance for a profile
  const {
    data: activeData,
    isLoading: loadingActive,
  } = useQuery({
    queryKey: ["guidance-active", activeProfileId],
    queryFn: () => guidanceApi.getActive(activeProfileId),
    enabled: !!activeProfileId,
    retry: false,
  });

  const {
    data: historyData,
    isLoading: loadingHistory,
  } = useQuery({
    queryKey: ["guidance-history", activeProfileId],
    queryFn: () => guidanceApi.getHistory(activeProfileId, 20),
    enabled: !!activeProfileId,
    retry: false,
  });

  const generateMutation = useMutation({
    mutationFn: (data: GuidanceRequest) => guidanceApi.generate(data),
    onSuccess: (guidance) => {
      queryClient.invalidateQueries({
        queryKey: ["guidance-active", activeProfileId],
      });
      queryClient.invalidateQueries({
        queryKey: ["guidance-history", activeProfileId],
      });
      setSelectedGuidance(guidance);
    },
  });

  function handleProfileChange(profileId: string) {
    setActiveProfileId(profileId);
    setSelectedGuidance(null);
  }

  function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    generateMutation.mutate({
      profile_id: activeProfileId,
      loan_purpose: purpose,
      requested_amount: Number(amount),
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">
          Credit Guidance
        </h2>
        <p className="text-sm text-gray-500">
          AI-powered loan recommendations tailored to each borrower
        </p>
      </div>

      {/* Profile selector */}
      <Card>
        <div className="space-y-3">
          <Select
            label="Select Borrower Profile"
            value={activeProfileId}
            onChange={(e) => handleProfileChange(e.target.value)}
            options={
              loadingProfiles
                ? [{ value: "", label: "Loading profiles…" }]
                : profiles.map((p) => ({
                    value: p.profile_id,
                    label: `${p.name} — ${p.location} (${formatEnum(p.occupation)})`,
                  }))
            }
          />
          {selectedProfile && (
            <div className="flex items-center gap-2 rounded-lg bg-brand-50 border border-brand-200 px-3 py-2">
              <User className="h-4 w-4 text-brand-600" />
              <span className="text-sm font-medium text-brand-700">
                {selectedProfile.name}
              </span>
              <span className="text-xs text-brand-500">
                {selectedProfile.location} · {formatEnum(selectedProfile.occupation)}
              </span>
            </div>
          )}
        </div>
      </Card>

      {!activeProfileId && (
        <EmptyState
          icon={<Lightbulb className="h-12 w-12" />}
          title="Select a borrower"
          description="Choose a borrower profile above to generate personalized credit guidance."
        />
      )}

      {activeProfileId && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Left: generate + history */}
          <div className="lg:col-span-1 space-y-6">
            {/* Generation form */}
            <Card>
              <CardTitle className="mb-4">Generate Guidance</CardTitle>
              <form onSubmit={handleGenerate} className="space-y-4">
                <Select
                  label="Loan Purpose"
                  value={purpose}
                  onChange={(e) =>
                    setPurpose(e.target.value as LoanPurpose)
                  }
                  options={PURPOSE_OPTIONS}
                />
                <Input
                  label="Requested Amount (₹)"
                  type="number"
                  min={1000}
                  step={1000}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
                <Button
                  type="submit"
                  className="w-full"
                  loading={generateMutation.isPending}
                  icon={<Lightbulb className="h-4 w-4" />}
                >
                  Generate
                </Button>
              </form>
              {generateMutation.isError && (
                <AlertBanner
                  variant="error"
                  message="Generation failed"
                  className="mt-3"
                />
              )}
            </Card>

            {/* Active guidance list */}
            <Card>
              <CardTitle className="mb-4">
                Active Guidance ({activeData?.items?.length ?? 0})
              </CardTitle>
              {loadingActive && <PageSpinner />}
              {!loadingActive &&
                (!activeData?.items || activeData.items.length === 0) && (
                  <p className="text-sm text-gray-500 py-4 text-center">
                    No active guidance
                  </p>
                )}
              <div className="space-y-2">
                {activeData?.items?.map((g) => (
                  <GuidanceSummaryRow
                    key={g.guidance_id}
                    guidance={g}
                    selected={
                      selectedGuidance?.guidance_id === g.guidance_id
                    }
                    onSelect={() => setSelectedGuidance(g)}
                  />
                ))}
              </div>
            </Card>

            {/* History list */}
            <Card>
              <CardTitle className="mb-4">History</CardTitle>
              {loadingHistory && <PageSpinner />}
              <div className="max-h-64 overflow-y-auto space-y-2">
                {historyData?.items?.map((g) => (
                  <GuidanceSummaryRow
                    key={g.guidance_id}
                    guidance={g}
                    selected={
                      selectedGuidance?.guidance_id === g.guidance_id
                    }
                    onSelect={() => setSelectedGuidance(g)}
                  />
                ))}
              </div>
            </Card>
          </div>

          {/* Right: detail */}
          <div className="lg:col-span-2">
            {selectedGuidance ? (
              <GuidanceDetail guidance={selectedGuidance} />
            ) : (
              <Card className="flex items-center justify-center h-96">
                <p className="text-sm text-gray-400">
                  Select or generate guidance to view details
                </p>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Guidance Summary Row ──────────────────────────────────────────────────

interface GuidanceSummaryRowProps {
  guidance: CreditGuidance;
  selected: boolean;
  onSelect: () => void;
}

function GuidanceSummaryRow({
  guidance,
  selected,
  onSelect,
}: GuidanceSummaryRowProps) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full rounded-lg border p-3 text-left transition-colors",
        selected
          ? "border-brand-500 bg-brand-50"
          : "border-gray-200 hover:bg-gray-50",
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-900 truncate">
          {formatEnum(guidance.loan_purpose)}
        </span>
        <Badge
          label={guidance.status}
          colorClass={
            GUIDANCE_STATUS_COLORS[guidance.status] ??
            "bg-gray-100 text-gray-700"
          }
        />
      </div>
      <div className="mt-1 flex items-center justify-between">
        <span className="text-xs text-gray-500">
          {formatCurrency(guidance.requested_amount)}
        </span>
        <span className="text-xs text-gray-400">
          {formatDate(guidance.created_at)}
        </span>
      </div>
    </button>
  );
}

// ─── Guidance Detail ───────────────────────────────────────────────────────

function GuidanceDetail({ guidance }: { guidance: CreditGuidance }) {
  return (
    <div className="space-y-5">
      {/* Header */}
      <Card>
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {formatEnum(guidance.loan_purpose)}
            </h3>
            <p className="text-sm text-gray-500">
              Generated {formatDate(guidance.created_at)} · Valid until{" "}
              {formatDate(guidance.expires_at ?? "")}
            </p>
          </div>
          <Badge
            label={guidance.status}
            colorClass={
              GUIDANCE_STATUS_COLORS[guidance.status] ??
              "bg-gray-100 text-gray-700"
            }
          />
        </div>
      </Card>

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Requested"
          value={formatCurrency(guidance.requested_amount)}
          icon={<IndianRupee className="h-5 w-5" />}
        />
        <StatCard
          label="Recommended Range"
          value={`${formatCurrency(guidance.recommended_amount.min_amount)} – ${formatCurrency(guidance.recommended_amount.max_amount)}`}
          icon={<IndianRupee className="h-5 w-5" />}
        />
        {guidance.risk_summary && (
          <StatCard
            label="Risk Score"
            value={`${guidance.risk_summary.risk_score}`}
            subtitle={formatEnum(guidance.risk_summary.risk_category)}
            icon={<ShieldCheck className="h-5 w-5" />}
          />
        )}
        {guidance.suggested_terms && (
          <StatCard
            label="Recommended EMI"
            value={formatCurrency(guidance.suggested_terms.emi_amount)}
            subtitle={`${guidance.suggested_terms.tenure_months} months`}
            icon={<CalendarCheck className="h-5 w-5" />}
          />
        )}
      </div>

      {/* Optimal timing */}
      {guidance.optimal_timing && (
        <Card>
          <CardTitle className="mb-3">Optimal Timing</CardTitle>
          <div className="rounded-lg bg-gray-50 p-4">
            <div className="flex items-center gap-3 mb-2">
              <Clock className="h-5 w-5 text-brand-600" />
              <span className="font-medium text-gray-900">
                {getMonthName(guidance.optimal_timing.start_month)}{" "}
                {guidance.optimal_timing.start_year} –{" "}
                {getMonthName(guidance.optimal_timing.end_month)}{" "}
                {guidance.optimal_timing.end_year}
              </span>
              <Badge
                label={formatEnum(guidance.optimal_timing.suitability)}
                colorClass={
                  TIMING_COLORS[guidance.optimal_timing.suitability] ??
                  "bg-gray-100 text-gray-700"
                }
              />
            </div>
            <p className="text-sm text-gray-600">
              {guidance.optimal_timing.reason}
            </p>
            <p className="mt-1 text-sm">
              Expected surplus:{" "}
              <span className="font-medium text-brand-700">
                {formatCurrency(guidance.optimal_timing.expected_surplus)}
              </span>
            </p>
          </div>
        </Card>
      )}

      {/* Suggested terms */}
      {guidance.suggested_terms && (
        <Card>
          <CardTitle className="mb-3">Suggested Loan Terms</CardTitle>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p className="text-xs text-gray-500">Tenure</p>
              <p className="font-medium text-gray-900">
                {guidance.suggested_terms.tenure_months} months
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">EMI Amount</p>
              <p className="font-medium text-gray-900">
                {formatCurrency(guidance.suggested_terms.emi_amount)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Total Repayment</p>
              <p className="font-medium text-gray-900">
                {formatCurrency(guidance.suggested_terms.total_repayment)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Interest Rate</p>
              <p className="font-medium text-gray-900">
                {guidance.suggested_terms.interest_rate_max_pct}%
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Risk summary */}
      {guidance.risk_summary && (
        <Card>
          <CardTitle className="mb-3">Risk Summary</CardTitle>
          <div className="flex items-center gap-4 mb-3">
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  "h-3 w-3 rounded-full",
                  guidance.risk_summary.risk_category === "LOW"
                    ? "bg-green-500"
                    : guidance.risk_summary.risk_category === "MEDIUM"
                      ? "bg-yellow-500"
                      : guidance.risk_summary.risk_category === "HIGH"
                        ? "bg-orange-500"
                        : "bg-red-500",
                )}
              />
              <span className="font-medium text-gray-900">
                {formatEnum(guidance.risk_summary.risk_category)} (
                {guidance.risk_summary.risk_score})
              </span>
            </div>
          </div>
          <ul className="space-y-1.5">
            {guidance.risk_summary.key_risk_factors.map((r, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-sm text-gray-600"
              >
                <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-gray-400" />
                {r}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Alternatives */}
      {guidance.alternative_options.length > 0 && (
        <Card>
          <CardTitle className="mb-4">Alternative Options</CardTitle>
          <div className="space-y-4">
            {guidance.alternative_options.map((alt, i) => (
              <div key={i} className="rounded-lg border border-gray-200 p-4">
                <p className="font-medium text-gray-900">{alt.description}</p>
                <p className="mt-1 text-sm text-gray-500">
                  {formatCurrency(alt.estimated_amount)} · {alt.timing}
                </p>
                <div className="mt-3 grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-medium text-green-700">Advantages</p>
                    <ul className="mt-1 space-y-1">
                      {alt.advantages.map((p, j) => (
                        <li
                          key={j}
                          className="flex items-start gap-1 text-xs text-gray-600"
                        >
                          <span className="text-green-500">+</span> {p}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-red-700">Disadvantages</p>
                    <ul className="mt-1 space-y-1">
                      {alt.disadvantages.map((c, j) => (
                        <li
                          key={j}
                          className="flex items-start gap-1 text-xs text-gray-600"
                        >
                          <span className="text-red-500">−</span> {c}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Explanation */}
      {guidance.explanation && (
        <Card>
          <CardTitle className="mb-4">Explanation</CardTitle>
          <p className="text-sm text-gray-700 mb-4">
            {guidance.explanation.summary}
          </p>

          {/* Reasoning steps */}
          <div className="relative space-y-4 pl-6 before:absolute before:left-2.5 before:top-0 before:h-full before:w-px before:bg-gray-200">
            {guidance.explanation.reasoning_steps.map((step) => (
              <div key={step.step_number} className="relative">
                <span className="absolute -left-6 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-brand-100 text-[10px] font-bold text-brand-700">
                  {step.step_number}
                </span>
                <p className="text-sm font-medium text-gray-900">
                  {step.factor}
                </p>
                <p className="text-sm text-gray-600">{step.observation}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  Impact: {step.impact}
                </p>
              </div>
            ))}
          </div>

          {/* Caveats */}
          {guidance.explanation.caveats.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-medium text-amber-600 mb-1">
                Caveats
              </p>
              <ul className="space-y-1">
                {guidance.explanation.caveats.map((c, i) => (
                  <li
                    key={i}
                    className="text-xs text-amber-600 flex items-start gap-1"
                  >
                    <span>⚠</span> {c}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
