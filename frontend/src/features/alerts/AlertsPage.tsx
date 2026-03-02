import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  CheckCircle,
  ChevronUp,
  Search,
  Play,
} from "lucide-react";
import { alertApi } from "@/api";
import {
  Button,
  Card,
  Input,
  Badge,
  PageSpinner,
  AlertBanner,
  EmptyState,
} from "@/components/ui";
import { formatDate } from "@/lib/utils";
import { ALERT_COLORS } from "@/lib/colors";
import { cn } from "@/lib/utils";
import type { Alert } from "@/types";

export function AlertsPage() {
  const [profileInput, setProfileInput] = useState("");
  const [activeProfileId, setActiveProfileId] = useState("");
  const [tab, setTab] = useState<"active" | "all">("active");
  const queryClient = useQueryClient();

  const { data: activeAlerts, isLoading: loadingActive } = useQuery({
    queryKey: ["alerts-active", activeProfileId],
    queryFn: () => alertApi.getActiveAlerts(activeProfileId),
    enabled: !!activeProfileId && tab === "active",
    retry: false,
  });

  const { data: allAlerts, isLoading: loadingAll } = useQuery({
    queryKey: ["alerts-all", activeProfileId],
    queryFn: () => alertApi.listByProfile(activeProfileId, 50),
    enabled: !!activeProfileId && tab === "all",
    retry: false,
  });

  const monitorMutation = useMutation({
    mutationFn: () => alertApi.monitor({ profile_id: activeProfileId }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["alerts-active", activeProfileId],
      });
      queryClient.invalidateQueries({
        queryKey: ["alerts-all", activeProfileId],
      });
    },
  });

  const acknowledgeMutation = useMutation({
    mutationFn: (alertId: string) => alertApi.acknowledge(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["alerts-active", activeProfileId],
      });
    },
  });

  const resolveMutation = useMutation({
    mutationFn: (alertId: string) => alertApi.resolve(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["alerts-active", activeProfileId],
      });
    },
  });

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setActiveProfileId(profileInput);
  }

  const alerts =
    tab === "active" ? activeAlerts?.alerts : allAlerts?.alerts;
  const isLoading = tab === "active" ? loadingActive : loadingAll;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">
          Early Warning & Alerts
        </h2>
        <p className="text-sm text-gray-500">
          Monitor borrower risk and manage alerts
        </p>
      </div>

      {/* Search + Monitor */}
      <Card>
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="flex-1">
            <Input
              placeholder="Enter borrower profile ID…"
              value={profileInput}
              onChange={(e) => setProfileInput(e.target.value)}
            />
          </div>
          <Button type="submit" icon={<Search className="h-4 w-4" />}>
            Search
          </Button>
          {activeProfileId && (
            <Button
              type="button"
              variant="outline"
              icon={<Play className="h-4 w-4" />}
              loading={monitorMutation.isPending}
              onClick={() => monitorMutation.mutate()}
            >
              Monitor
            </Button>
          )}
        </form>
      </Card>

      {monitorMutation.isError && (
        <AlertBanner variant="error" message="Monitoring check failed" />
      )}
      {monitorMutation.isSuccess && (
        <AlertBanner
          variant="success"
          message="Monitoring completed. Any new alerts have been generated."
        />
      )}

      {activeProfileId && (
        <>
          {/* Tab selector */}
          <div className="flex gap-1 rounded-lg bg-gray-100 p-1 w-fit">
            {(["active", "all"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
                  tab === t
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-500 hover:text-gray-700",
                )}
              >
                {t === "active" ? "Active Alerts" : "All Alerts"}
              </button>
            ))}
          </div>

          {isLoading && <PageSpinner />}

          {!isLoading && (!alerts || alerts.length === 0) && (
            <EmptyState
              icon={<Bell className="h-12 w-12" />}
              title={
                tab === "active"
                  ? "No active alerts"
                  : "No alerts found"
              }
              description="No alerts to display for this borrower."
            />
          )}

          {alerts && alerts.length > 0 && (
            <div className="space-y-3">
              {alerts.map((alert) => (
                <AlertCard
                  key={alert.alert_id}
                  alert={alert}
                  onAcknowledge={() =>
                    acknowledgeMutation.mutate(alert.alert_id)
                  }
                  onResolve={() => resolveMutation.mutate(alert.alert_id)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── Alert Card Component ─────────────────────────────────────────────────

interface AlertCardProps {
  alert: Alert;
  onAcknowledge: () => void;
  onResolve: () => void;
}

function AlertCard({ alert, onAcknowledge, onResolve }: AlertCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card
      className={cn(
        "border-l-4",
        alert.severity === "CRITICAL"
          ? "border-l-red-500"
          : alert.severity === "WARNING"
            ? "border-l-yellow-500"
            : "border-l-blue-500",
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              label={alert.severity}
              colorClass={ALERT_COLORS[alert.severity]}
            />
            <Badge label={alert.alert_type} />
            <Badge
              label={alert.status}
              colorClass={
                alert.status === "RESOLVED"
                  ? "bg-green-100 text-green-700"
                  : alert.status === "ACKNOWLEDGED"
                    ? "bg-blue-100 text-blue-700"
                    : "bg-gray-100 text-gray-700"
              }
            />
          </div>
          <p className="mt-2 text-sm text-gray-700">{alert.message}</p>
          <p className="mt-1 text-xs text-gray-400">
            {formatDate(alert.created_at)}
          </p>
        </div>

        {alert.status === "ACTIVE" && (
          <div className="flex gap-2 ml-4">
            <Button
              variant="outline"
              size="sm"
              onClick={onAcknowledge}
              icon={<CheckCircle className="h-3.5 w-3.5" />}
            >
              Ack
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onResolve}
            >
              Resolve
            </Button>
          </div>
        )}
      </div>

      {/* Expandable recommendations */}
      {alert.recommendations.length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700"
          >
            <ChevronUp
              className={cn(
                "h-3.5 w-3.5 transition-transform",
                expanded ? "" : "rotate-180",
              )}
            />
            {expanded ? "Hide" : "Show"} Recommendations (
            {alert.recommendations.length})
          </button>

          {expanded && (
            <div className="mt-2 space-y-2">
              {alert.recommendations.map((rec, i) => (
                <div
                  key={i}
                  className="rounded-lg bg-gray-50 p-3 text-sm"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
                      {rec.priority}
                    </span>
                    <span className="font-medium text-gray-900">
                      {rec.action}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">
                    Impact: {rec.expected_impact} · Timeline: {rec.timeline}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
