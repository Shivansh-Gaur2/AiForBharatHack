import { Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardTitle } from "@/components/ui";
import { dashboardApi } from "@/api/dashboard";

const CATEGORY_META: Record<string, { label: string; color: string }> = {
  LOW: { label: "Low", color: "bg-green-500" },
  MEDIUM: { label: "Medium", color: "bg-yellow-500" },
  HIGH: { label: "High", color: "bg-orange-500" },
  VERY_HIGH: { label: "Very High", color: "bg-red-500" },
};

export function RiskOverview() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "risk"],
    queryFn: dashboardApi.riskStats,
    staleTime: 60_000,
  });

  const distribution = data?.distribution ?? {};
  const total = Object.values(distribution).reduce((s, c) => s + c, 0);

  const rows = Object.entries(CATEGORY_META).map(([key, meta]) => ({
    category: meta.label,
    count: distribution[key] ?? 0,
    pct: total > 0 ? Math.round(((distribution[key] ?? 0) / total) * 100) : 0,
    color: meta.color,
  }));

  return (
    <Card>
      <CardTitle className="mb-4">Risk Distribution</CardTitle>

      {isLoading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
        </div>
      ) : total === 0 ? (
        <div className="py-6 text-center text-sm text-gray-400">
          No risk assessments yet.
        </div>
      ) : (
        <>
          {/* Stacked bar */}
          <div className="flex h-4 overflow-hidden rounded-full bg-gray-100">
            {rows.map(({ category, pct, color }) => (
              <div
                key={category}
                className={color}
                style={{ width: `${pct}%` }}
                title={`${category}: ${pct}%`}
              />
            ))}
          </div>

          {/* Legend */}
          <div className="mt-4 space-y-2">
            {rows.map(({ category, count, pct, color }) => (
              <div key={category} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className={`h-3 w-3 rounded-full ${color}`} />
                  <span className="text-gray-600">{category}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-medium text-gray-900">{count}</span>
                  <span className="w-10 text-right text-gray-400">{pct}%</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}
