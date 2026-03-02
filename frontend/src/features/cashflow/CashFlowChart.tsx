import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
} from "recharts";
import { Card, CardTitle } from "@/components/ui";
import { getMonthName, formatCurrency } from "@/lib/utils";
import type { MonthlyProjection, UncertaintyBand } from "@/types";

interface Props {
  projections: MonthlyProjection[];
  uncertaintyBands: UncertaintyBand[];
}

export function CashFlowChart({ projections, uncertaintyBands }: Props) {
  const chartData = projections.map((p) => {
    const band = uncertaintyBands.find(
      (b) => b.month === p.month && b.year === p.year,
    );
    return {
      name: `${getMonthName(p.month)} ${String(p.year).slice(2)}`,
      Inflow: p.projected_inflow,
      Outflow: p.projected_outflow,
      "Net Cash Flow": p.net_cash_flow,
      lower: band?.lower_bound ?? p.net_cash_flow,
      upper: band?.upper_bound ?? p.net_cash_flow,
    };
  });

  return (
    <Card>
      <CardTitle className="mb-4">Cash Flow Forecast</CardTitle>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorInflow" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorOutflow" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorNet" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
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

            {/* Uncertainty band */}
            <Area
              type="monotone"
              dataKey="upper"
              stroke="none"
              fill="#93c5fd"
              fillOpacity={0.15}
              name="Upper Bound"
            />
            <Area
              type="monotone"
              dataKey="lower"
              stroke="none"
              fill="#ffffff"
              fillOpacity={1}
              name="Lower Bound"
            />

            <Area
              type="monotone"
              dataKey="Inflow"
              stroke="#22c55e"
              fill="url(#colorInflow)"
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="Outflow"
              stroke="#ef4444"
              fill="url(#colorOutflow)"
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="Net Cash Flow"
              stroke="#3b82f6"
              fill="url(#colorNet)"
              strokeWidth={2.5}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
