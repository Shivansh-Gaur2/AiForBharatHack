import { Card, CardTitle } from "@/components/ui";

const MOCK_DISTRIBUTION = [
  { category: "Low", count: 52, pct: 41, color: "bg-green-500" },
  { category: "Medium", count: 48, pct: 37, color: "bg-yellow-500" },
  { category: "High", count: 22, pct: 17, color: "bg-orange-500" },
  { category: "Very High", count: 6, pct: 5, color: "bg-red-500" },
];

export function RiskOverview() {
  return (
    <Card>
      <CardTitle className="mb-4">Risk Distribution</CardTitle>

      {/* Stacked bar */}
      <div className="flex h-4 overflow-hidden rounded-full bg-gray-100">
        {MOCK_DISTRIBUTION.map(({ category, pct, color }) => (
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
        {MOCK_DISTRIBUTION.map(({ category, count, pct, color }) => (
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
    </Card>
  );
}
