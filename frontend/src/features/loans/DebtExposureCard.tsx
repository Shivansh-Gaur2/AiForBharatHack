import { useQuery } from "@tanstack/react-query";
import { loanApi } from "@/api";
import { Card, CardTitle, Badge, StatCard, PageSpinner, AlertBanner } from "@/components/ui";
import { formatCurrency, formatPercent, formatEnum } from "@/lib/utils";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

interface Props {
  profileId: string;
}

const SOURCE_COLORS = ["#22c55e", "#3b82f6", "#f59e0b"];

export function DebtExposureCard({ profileId }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["exposure", profileId],
    queryFn: () => loanApi.getExposure(profileId),
    enabled: !!profileId,
  });

  if (isLoading) return <PageSpinner />;
  if (error) return <AlertBanner variant="error" message="Failed to load exposure" />;
  if (!data) return null;

  const chartData = data.by_source.map((s) => ({
    name: formatEnum(s.source_type),
    value: s.total_outstanding,
  }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total Outstanding"
          value={formatCurrency(data.total_outstanding)}
        />
        <StatCard
          label="Monthly Obligations"
          value={formatCurrency(data.monthly_obligations)}
        />
        <StatCard
          label="Debt-to-Income"
          value={formatPercent(data.debt_to_income_ratio)}
        />
        <StatCard
          label="Credit Utilisation"
          value={formatPercent(data.credit_utilisation)}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle className="mb-4">Exposure by Source</CardTitle>
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={SOURCE_COLORS[i % SOURCE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: number) => formatCurrency(v)}
                  contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 12 }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardTitle className="mb-4">Source Breakdown</CardTitle>
          <div className="space-y-4">
            {data.by_source.map((s, i) => (
              <div key={s.source_type} className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 rounded-full"
                      style={{ backgroundColor: SOURCE_COLORS[i % SOURCE_COLORS.length] }}
                    />
                    <Badge label={s.source_type} />
                  </div>
                  <span className="font-medium">{formatCurrency(s.total_outstanding)}</span>
                </div>
                <div className="text-xs text-gray-400">
                  {s.loan_count} loan(s) · {formatCurrency(s.monthly_obligation)}/month
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
