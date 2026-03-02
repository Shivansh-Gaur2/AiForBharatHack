import { AlertCircle, AlertTriangle, Info } from "lucide-react";
import { Card, CardHeader, CardTitle, Badge } from "@/components/ui";
import { cn } from "@/lib/utils";

interface MockAlert {
  id: string;
  borrower: string;
  type: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  message: string;
  time: string;
}

const MOCK_ALERTS: MockAlert[] = [
  {
    id: "1",
    borrower: "Ramesh Kumar",
    type: "REPAYMENT_STRESS",
    severity: "CRITICAL",
    message: "Missed 2 consecutive repayments on crop loan",
    time: "2 hours ago",
  },
  {
    id: "2",
    borrower: "Sunita Devi",
    type: "INCOME_DEVIATION",
    severity: "WARNING",
    message: "Income 40% below seasonal average",
    time: "5 hours ago",
  },
  {
    id: "3",
    borrower: "Mohan Singh",
    type: "WEATHER_RISK",
    severity: "WARNING",
    message: "Drought alert in district — crop yield at risk",
    time: "1 day ago",
  },
  {
    id: "4",
    borrower: "Lakshmi Bai",
    type: "OVER_INDEBTEDNESS",
    severity: "INFO",
    message: "Debt-to-income ratio approaching threshold",
    time: "2 days ago",
  },
];

const iconMap = {
  CRITICAL: <AlertCircle className="h-5 w-5 text-red-500" />,
  WARNING: <AlertTriangle className="h-5 w-5 text-yellow-500" />,
  INFO: <Info className="h-5 w-5 text-blue-500" />,
};

const badgeColors = {
  CRITICAL: "bg-red-100 text-red-700",
  WARNING: "bg-yellow-100 text-yellow-700",
  INFO: "bg-blue-100 text-blue-700",
};

export function RecentAlerts() {
  return (
    <Card>
      <CardHeader className="mb-4">
        <CardTitle>Recent Alerts</CardTitle>
        <a href="/alerts" className="text-sm font-medium text-brand-600 hover:text-brand-700">
          View all →
        </a>
      </CardHeader>

      <div className="divide-y divide-gray-100">
        {MOCK_ALERTS.map((alert) => (
          <div
            key={alert.id}
            className="flex items-start gap-3 py-3 first:pt-0 last:pb-0"
          >
            {iconMap[alert.severity]}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {alert.borrower}
                </p>
                <Badge
                  label={alert.severity}
                  colorClass={cn(badgeColors[alert.severity])}
                />
              </div>
              <p className="mt-0.5 text-sm text-gray-500">{alert.message}</p>
            </div>
            <span className="flex-shrink-0 text-xs text-gray-400">
              {alert.time}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
