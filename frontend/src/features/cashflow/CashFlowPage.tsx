import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { TrendingUp, RefreshCw, CalendarClock, User } from "lucide-react";
import { cashflowApi, profileApi } from "@/api";
import {
  Button,
  Card,
  CardTitle,
  Select,
  StatCard,
  PageSpinner,
  AlertBanner,
  EmptyState,
  Badge,
} from "@/components/ui";
import { formatCurrency, formatPercent, getMonthName } from "@/lib/utils";
import { TIMING_COLORS } from "@/lib/colors";
import { CashFlowChart } from "./CashFlowChart";

export function CashFlowPage() {
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
    data: forecast,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["cashflow-forecast", activeProfileId],
    queryFn: () => cashflowApi.getLatestForecast(activeProfileId),
    enabled: !!activeProfileId,
    retry: false,
  });

  const generateMutation = useMutation({
    mutationFn: () =>
      cashflowApi.generateForecast({
        profile_id: activeProfileId,
        horizon_months: 12,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["cashflow-forecast", activeProfileId],
      });
    },
  });

  function handleProfileChange(profileId: string) {
    setActiveProfileId(profileId);
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">
          Cash Flow Analysis
        </h2>
        <p className="text-sm text-gray-500">
          Predict future cash flows and find optimal borrowing windows
        </p>
      </div>

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
              loading={generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
            >
              Generate
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

      {generateMutation.isError && (
        <AlertBanner
          variant="error"
          message={
            generateMutation.error instanceof Error
              ? generateMutation.error.message
              : "Forecast generation failed"
          }
        />
      )}

      {isLoading && <PageSpinner />}
      {error && activeProfileId && (
        <EmptyState
          icon={<TrendingUp className="h-12 w-12" />}
          title="No forecast available"
          description="Generate a cash flow forecast for this profile."
          action={
            <Button
              loading={generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
            >
              Generate Forecast
            </Button>
          }
        />
      )}

      {forecast && (
        <>
          {/* Capacity KPIs */}
          {forecast.repayment_capacity && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                label="Monthly Disposable"
                value={formatCurrency(
                  forecast.repayment_capacity.monthly_disposable_income,
                )}
              />
              <StatCard
                label="Max EMI Affordable"
                value={formatCurrency(
                  forecast.repayment_capacity.max_emi_affordable,
                )}
              />
              <StatCard
                label="Recommended EMI"
                value={formatCurrency(
                  forecast.repayment_capacity.recommended_emi,
                )}
              />
              <StatCard
                label="Safety Margin"
                value={formatPercent(
                  forecast.repayment_capacity.safety_margin,
                )}
              />
            </div>
          )}

          {/* Cash flow chart */}
          <CashFlowChart
            projections={forecast.monthly_projections}
            uncertaintyBands={forecast.uncertainty_bands}
          />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Timing windows */}
            <Card>
              <CardTitle className="mb-4 flex items-center gap-2">
                <CalendarClock className="h-5 w-5" />
                Optimal Borrowing Windows
              </CardTitle>
              {forecast.timing_windows.length === 0 ? (
                <p className="text-sm text-gray-400">
                  No timing windows identified.
                </p>
              ) : (
                <div className="space-y-3">
                  {forecast.timing_windows.map((tw, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-gray-100 p-3"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-900">
                          {getMonthName(tw.start_month)} {tw.start_year} –{" "}
                          {getMonthName(tw.end_month)} {tw.end_year}
                        </span>
                        <Badge
                          label={tw.suitability}
                          colorClass={
                            TIMING_COLORS[tw.suitability] ??
                            "bg-gray-100 text-gray-700"
                          }
                        />
                      </div>
                      <p className="text-xs text-gray-500">{tw.reason}</p>
                      <p className="mt-1 text-xs text-green-600">
                        Expected surplus: {formatCurrency(tw.expected_surplus)}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Seasonal patterns */}
            <Card>
              <CardTitle className="mb-4">Seasonal Patterns</CardTitle>
              {forecast.seasonal_patterns.length === 0 ? (
                <p className="text-sm text-gray-400">
                  No seasonal patterns detected.
                </p>
              ) : (
                <div className="space-y-3">
                  {forecast.seasonal_patterns.map((sp, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-gray-100 p-3"
                    >
                      <Badge label={sp.season} colorClass="bg-earth-100 text-earth-700" />
                      <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                        <div>
                          <p className="text-gray-400">Avg Inflow</p>
                          <p className="font-medium text-green-600">
                            {formatCurrency(sp.avg_inflow)}
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-400">Avg Outflow</p>
                          <p className="font-medium text-red-600">
                            {formatCurrency(sp.avg_outflow)}
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-400">Net Flow</p>
                          <p
                            className={`font-medium ${sp.net_flow >= 0 ? "text-green-600" : "text-red-600"}`}
                          >
                            {formatCurrency(sp.net_flow)}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* Assumptions */}
          {forecast.assumptions.length > 0 && (
            <Card>
              <CardTitle className="mb-3">Key Assumptions</CardTitle>
              <ul className="space-y-1">
                {forecast.assumptions.map((a, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-gray-600"
                  >
                    <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-400" />
                    {a}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
