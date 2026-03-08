import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { ShieldAlert, RefreshCw, History, User } from "lucide-react";
import { riskApi, profileApi } from "@/api";
import {
  Button,
  Card,
  CardTitle,
  Select,
  Badge,
  StatCard,
  PageSpinner,
  AlertBanner,
  EmptyState,
} from "@/components/ui";
import { formatDate, formatPercent } from "@/lib/utils";
import { RISK_COLORS } from "@/lib/colors";
import { RiskGauge } from "./RiskGauge";
import { RiskFactorsChart } from "./RiskFactorsChart";

export function RiskPage() {
  const [searchParams] = useSearchParams();
  const initialProfile = searchParams.get("profile") ?? "";
  const [activeProfileId, setActiveProfileId] = useState(initialProfile);
  const queryClient = useQueryClient();

  const { data: profilesData, isLoading: loadingProfiles } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => profileApi.list({ limit: 200 }),
  });
  const profiles = profilesData?.items ?? [];
  const selectedProfile = profiles.find((p) => p.profile_id === activeProfileId);

  const {
    data: assessment,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["risk", activeProfileId],
    queryFn: () => riskApi.getByProfile(activeProfileId),
    enabled: !!activeProfileId,
    retry: false,
  });

  const { data: history } = useQuery({
    queryKey: ["riskHistory", activeProfileId],
    queryFn: () => riskApi.getHistory(activeProfileId, 10),
    enabled: !!activeProfileId,
  });

  const assessMutation = useMutation({
    mutationFn: () => riskApi.assess({ profile_id: activeProfileId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risk", activeProfileId] });
      queryClient.invalidateQueries({
        queryKey: ["riskHistory", activeProfileId],
      });
    },
  });

  function handleProfileChange(profileId: string) {
    setActiveProfileId(profileId);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            Risk Assessment
          </h2>
          <p className="text-sm text-gray-500">
            Evaluate borrower risk with AI-powered scoring
          </p>
        </div>
      </div>

      {/* Profile selector */}
      <Card>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <Select
              label="Select Borrower Profile"
              value={activeProfileId}
              onChange={(e) => handleProfileChange(e.target.value)}
              options={
                loadingProfiles
                  ? [{ value: "", label: "Loading profiles…" }]
                  : profiles.map((p) => ({
                      value: p.profile_id,
                      label: `${p.name} — ${p.location}`,
                    }))
              }
            />
          </div>
          {activeProfileId && (
            <Button
              type="button"
              variant="outline"
              icon={<RefreshCw className="h-4 w-4" />}
              loading={assessMutation.isPending}
              onClick={() => assessMutation.mutate()}
            >
              Re-assess
            </Button>
          )}
        </div>
        {selectedProfile && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-brand-50 border border-brand-200 px-3 py-2">
            <User className="h-4 w-4 text-brand-600" />
            <span className="text-sm font-medium text-brand-700">{selectedProfile.name}</span>
            <span className="text-xs text-brand-500">{selectedProfile.location}</span>
          </div>
        )}
      </Card>

      {assessMutation.isError && (
        <AlertBanner
          variant="error"
          message={
            assessMutation.error instanceof Error
              ? assessMutation.error.message
              : "Assessment failed"
          }
        />
      )}

      {isLoading && <PageSpinner />}
      {error && activeProfileId && (
        <EmptyState
          icon={<ShieldAlert className="h-12 w-12" />}
          title="No risk assessment found"
          description="Run a risk assessment for this profile to see results."
          action={
            <Button
              loading={assessMutation.isPending}
              onClick={() => assessMutation.mutate()}
            >
              Run Assessment
            </Button>
          }
        />
      )}

      {assessment && (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Risk Score"
              value={`${assessment.risk_score} / 1000`}
              icon={<ShieldAlert className="h-5 w-5" />}
            />
            <div className="flex items-center">
              <Card className="w-full flex items-center justify-center py-6">
                <Badge
                  label={assessment.risk_category}
                  colorClass={RISK_COLORS[assessment.risk_category]}
                  className="text-base px-4 py-1"
                />
              </Card>
            </div>
            <StatCard
              label="Confidence"
              value={formatPercent(assessment.confidence_level)}
            />
            <StatCard
              label="Valid Until"
              value={formatDate(assessment.valid_until)}
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Risk gauge */}
            <RiskGauge
              score={assessment.risk_score}
              category={assessment.risk_category}
            />

            {/* Factors chart */}
            <RiskFactorsChart factors={assessment.factors} />
          </div>

          {/* Explanation */}
          <Card>
            <CardTitle className="mb-4">Risk Explanation</CardTitle>
            <p className="text-sm text-gray-700 mb-4">
              {assessment.explanation.summary}
            </p>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <h4 className="text-sm font-medium text-gray-900 mb-2">
                  Key Factors
                </h4>
                <ul className="space-y-1">
                  {assessment.explanation.key_factors.map((f, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                      <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-orange-400" />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-900 mb-2">
                  Recommendations
                </h4>
                <ul className="space-y-1">
                  {assessment.explanation.recommendations.map((r, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                      <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-green-400" />
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Card>

          {/* History */}
          {history && history.length > 0 && (
            <Card>
              <CardTitle className="mb-4 flex items-center gap-2">
                <History className="h-5 w-5" />
                Assessment History
              </CardTitle>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 text-left text-xs text-gray-400">
                      <th className="pb-2">Date</th>
                      <th className="pb-2">Score</th>
                      <th className="pb-2">Category</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {history.map((h) => (
                      <tr key={h.assessment_id}>
                        <td className="py-2 text-gray-700">
                          {formatDate(h.assessed_at)}
                        </td>
                        <td className="py-2 font-medium">{h.risk_score}</td>
                        <td className="py-2">
                          <Badge
                            label={h.risk_category}
                            colorClass={RISK_COLORS[h.risk_category]}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
