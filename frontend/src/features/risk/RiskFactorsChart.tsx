import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Card, CardTitle } from "@/components/ui";
import { formatEnum } from "@/lib/utils";
import type { RiskFactor } from "@/types";

interface Props {
  factors: RiskFactor[];
}

function getBarColor(score: number): string {
  if (score < 250) return "#22c55e";
  if (score < 500) return "#eab308";
  if (score < 750) return "#f97316";
  return "#ef4444";
}

export function RiskFactorsChart({ factors }: Props) {
  const chartData = factors.map((f) => ({
    name: formatEnum(f.factor_type).replace(/\s/g, "\n"),
    score: f.score,
    weight: f.weight,
    weighted: f.weighted_score,
  }));

  return (
    <Card>
      <CardTitle className="mb-4">Risk Factors Breakdown</CardTitle>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" barSize={16}>
            <XAxis type="number" domain={[0, 1000]} tick={{ fontSize: 11 }} />
            <YAxis
              type="category"
              dataKey="name"
              width={100}
              tick={{ fontSize: 10 }}
            />
            <Tooltip
              contentStyle={{
                borderRadius: 8,
                border: "1px solid #e5e7eb",
                fontSize: 12,
              }}
              formatter={(v: number, name: string) => [
                `${v.toFixed(0)}`,
                name,
              ]}
            />
            <Bar dataKey="score" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={index} fill={getBarColor(entry.score)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
