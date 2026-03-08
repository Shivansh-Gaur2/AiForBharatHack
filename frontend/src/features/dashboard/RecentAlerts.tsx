import { AlertCircle, AlertTriangle, Info, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, Badge } from "@/components/ui";
import { dashboardApi, type RecentAlert } from "@/api/dashboard";
import { cn } from "@/lib/utils";

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

function timeAgo(dateStr: string): string {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function RecentAlerts() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "alerts"],
    queryFn: dashboardApi.alertStats,
    staleTime: 60_000,
  });

  const alerts: RecentAlert[] = data?.recent_alerts ?? [];

  return (
    <Card>
      <CardHeader className="mb-4">
        <CardTitle>Recent Alerts</CardTitle>
        <Link to="/alerts" className="text-sm font-medium text-brand-600 hover:text-brand-700">
          View all →
        </Link>
      </CardHeader>

      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
        </div>
      ) : alerts.length === 0 ? (
        <div className="py-8 text-center text-sm text-gray-400">
          No alerts yet. Create profiles and run monitoring to generate alerts.
        </div>
      ) : (
        <div className="divide-y divide-gray-100">
          {alerts.map((alert) => (
            <div
              key={alert.alert_id}
              className="flex items-start gap-3 py-3 first:pt-0 last:pb-0"
            >
              {iconMap[alert.severity] ?? iconMap.INFO}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {alert.title || alert.alert_type}
                  </p>
                  <Badge
                    label={alert.severity}
                    colorClass={cn(badgeColors[alert.severity] ?? badgeColors.INFO)}
                  />
                </div>
                <p className="mt-0.5 text-sm text-gray-500">
                  {alert.description || `Alert for profile ${alert.profile_id.slice(0, 8)}…`}
                </p>
              </div>
              <span className="flex-shrink-0 text-xs text-gray-400">
                {timeAgo(alert.created_at)}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
