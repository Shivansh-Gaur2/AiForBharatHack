import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Beaker, AlertTriangle, TrendingDown } from "lucide-react";
import { alertApi } from "@/api";
import {
  Button,
  Card,
  CardTitle,
  Input,
  Select,
  StatCard,
  AlertBanner,
  PageSpinner,
} from "@/components/ui";
import { formatCurrency, formatEnum, getMonthName } from "@/lib/utils";
import { ScenarioType } from "@/types";
import type { SimulationResult, ScenarioRequest } from "@/types";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
} from "recharts";

const SCENARIO_OPTIONS = Object.values(ScenarioType).map((v) => ({
  value: v,
  label: formatEnum(v),
}));

export function ScenarioPage() {
  const [profileId, setProfileId] = useState("");
  const [scenarioType, setScenarioType] = useState<ScenarioType>(
    ScenarioType.INCOME_SHOCK,
  );
  const [shockPct, setShockPct] = useState("30");
  const [duration, setDuration] = useState("3");

  const mutation = useMutation({
    mutationFn: (data: ScenarioRequest) => alertApi.simulate(data),
  });

  function handleRun(e: React.FormEvent) {
    e.preventDefault();
    const name = `${formatEnum(scenarioType)} — ${shockPct}% shock, ${duration}mth`;
    mutation.mutate({
      profile_id: profileId,
      scenario_type: scenarioType,
      name,
      income_reduction_pct: scenarioType === ScenarioType.INCOME_SHOCK || scenarioType === ScenarioType.COMBINED ? Number(shockPct) : 0,
      weather_adjustment: scenarioType === ScenarioType.WEATHER_IMPACT ? 1 - Number(shockPct) / 100 : 1.0,
      market_price_change_pct: scenarioType === ScenarioType.MARKET_VOLATILITY || scenarioType === ScenarioType.COMBINED ? -Number(shockPct) : 0,
      duration_months: Number(duration),
    });
  }

  const result: SimulationResult | undefined = mutation.data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">
          Scenario Simulation
        </h2>
        <p className="text-sm text-gray-500">
          Model income shocks and see their impact on repayment capacity
        </p>
      </div>

      <Card>
        <CardTitle className="mb-4">Configure Scenario</CardTitle>
        <form onSubmit={handleRun} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Input
              label="Profile ID"
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
              required
            />
            <Select
              label="Scenario Type"
              value={scenarioType}
              onChange={(e) => setScenarioType(e.target.value as ScenarioType)}
              options={SCENARIO_OPTIONS}
            />
            <Input
              label="Shock (%)"
              type="number"
              min={1}
              max={100}
              value={shockPct}
              onChange={(e) => setShockPct(e.target.value)}
            />
            <Input
              label="Duration (months)"
              type="number"
              min={1}
              max={24}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            />
          </div>
          <Button
            type="submit"
            loading={mutation.isPending}
            icon={<Beaker className="h-4 w-4" />}
          >
            Run Simulation
          </Button>
        </form>
      </Card>

      {mutation.isError && (
        <AlertBanner variant="error" message="Simulation failed" />
      )}
      {mutation.isPending && <PageSpinner />}

      {result && (
        <>
          {/* Impact KPIs */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Overall Risk"
              value={formatEnum(result.overall_risk_level)}
              icon={<AlertTriangle className="h-5 w-5" />}
            />
            <StatCard
              label="Baseline EMI Capacity"
              value={formatCurrency(result.capacity_impact.original_recommended_emi)}
            />
            <StatCard
              label="Stressed EMI Capacity"
              value={formatCurrency(result.capacity_impact.stressed_recommended_emi)}
            />
            <StatCard
              label="EMI Capacity Loss"
              value={`${result.capacity_impact.emi_reduction_pct.toFixed(1)}%`}
              icon={<TrendingDown className="h-5 w-5" />}
            />
          </div>

          {/* Additional stats row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard label="Months in Deficit" value={String(result.months_in_deficit)} />
            <StatCard label="Total Income Loss" value={formatCurrency(result.total_income_loss)} />
            <StatCard label="Coverage Ratio (Stressed)" value={result.capacity_impact.stressed_dscr.toFixed(2) + "x"} />
          </div>

          {/* Can service debt warning */}
          {!result.capacity_impact.can_still_repay && (
            <AlertBanner
              variant="error"
              title="Cannot Service Existing Debt"
              message="Under this scenario, the borrower would be unable to service their existing debt obligations."
            />
          )}

          {/* Projection chart */}
          <Card>
            <CardTitle className="mb-4">Scenario Projections</CardTitle>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={result.projections.map((p) => ({
                    name: `${getMonthName(p.month)} ${String(p.year).slice(2)}`,
                    "Baseline Income": p.baseline_inflow,
                    "Stressed Income": p.stressed_inflow,
                    "Net Impact": p.stressed_net,
                  }))}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    formatter={(v: number) => formatCurrency(v)}
                    contentStyle={{
                      borderRadius: 8,
                      border: "1px solid #e5e7eb",
                      fontSize: 12,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line
                    type="monotone"
                    dataKey="Baseline Income"
                    stroke="#22c55e"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="Stressed Income"
                    stroke="#ef4444"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="Net Impact"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Recommendations */}
          {result.recommendations.length > 0 && (
            <Card>
              <CardTitle className="mb-4">Recommendations</CardTitle>
              <div className="space-y-3">
                {result.recommendations.map((rec, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 rounded-lg bg-gray-50 p-4"
                  >
                    <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
                      {i + 1}
                    </span>
                    <div>
                      <p className="font-medium text-gray-900">{rec.recommendation}</p>
                      <p className="mt-0.5 text-sm text-gray-500">
                        {rec.rationale}
                      </p>
                      {rec.confidence && (
                        <span className="mt-1 inline-block text-xs text-brand-600 font-medium">
                          Confidence: {rec.confidence}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
