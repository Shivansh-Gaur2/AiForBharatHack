import { Card, CardTitle, Badge } from "@/components/ui";
import { formatPercent } from "@/lib/utils";
import type { VolatilityMetrics } from "@/types";

interface Props {
  metrics: VolatilityMetrics;
}

const levelColors: Record<string, string> = {
  LOW: "bg-green-100 text-green-700",
  MEDIUM: "bg-yellow-100 text-yellow-700",
  HIGH: "bg-red-100 text-red-700",
};

export function VolatilityCard({ metrics }: Props) {
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <CardTitle>Income Volatility</CardTitle>
        <Badge
          label={metrics.volatility_level}
          colorClass={levelColors[metrics.volatility_level] ?? ""}
        />
      </div>

      <dl className="space-y-3 text-sm">
        <div className="flex justify-between">
          <dt className="text-gray-500">Coefficient of Variation</dt>
          <dd className="font-medium">
            {formatPercent(metrics.coefficient_of_variation)}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Income Range Ratio</dt>
          <dd className="font-medium">
            {metrics.income_range_ratio.toFixed(2)}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Seasonal Variance</dt>
          <dd className="font-medium">
            {formatPercent(metrics.seasonal_variance)}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Months Below Average</dt>
          <dd className="font-medium">{metrics.months_below_average}</dd>
        </div>
      </dl>

      {/* Visual bar */}
      <div className="mt-4">
        <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
          <span>Low</span>
          <span>High</span>
        </div>
        <div className="h-2 rounded-full bg-gray-100">
          <div
            className="h-2 rounded-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500"
            style={{
              width: `${Math.min(metrics.coefficient_of_variation * 200, 100)}%`,
            }}
          />
        </div>
      </div>
    </Card>
  );
}
