import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, MapPin, Briefcase } from "lucide-react";
import { profileApi } from "@/api";
import {
  Button,
  Card,
  Badge,
  PageSpinner,
  AlertBanner,
  EmptyState,
} from "@/components/ui";
import { formatDate, formatEnum } from "@/lib/utils";
import { RISK_COLORS } from "@/lib/colors";

export function ProfileListPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => profileApi.list({ limit: 50 }),
  });

  if (isLoading) return <PageSpinner />;
  if (error)
    return (
      <AlertBanner
        variant="error"
        message={error instanceof Error ? error.message : "Failed to load profiles"}
      />
    );

  const profiles = data?.items ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            Borrower Profiles
          </h2>
          <p className="text-sm text-gray-500">
            {profiles.length} profiles registered
          </p>
        </div>
        <Link to="/profiles/new">
          <Button icon={<Plus className="h-4 w-4" />}>New Profile</Button>
        </Link>
      </div>

      {/* Profiles grid */}
      {profiles.length === 0 ? (
        <EmptyState
          title="No profiles yet"
          description="Create a borrower profile to get started with credit assessment."
          action={
            <Link to="/profiles/new">
              <Button icon={<Plus className="h-4 w-4" />}>
                Create First Profile
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {profiles.map((p) => (
            <Link key={p.profile_id} to={`/profiles/${p.profile_id}`}>
              <Card className="transition-shadow hover:shadow-md cursor-pointer">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">{p.name}</h3>
                    <div className="mt-1 flex items-center gap-1 text-sm text-gray-500">
                      <MapPin className="h-3.5 w-3.5" />
                      {p.location}
                    </div>
                  </div>
                  {p.volatility_level && (
                    <Badge
                      label={p.volatility_level}
                      colorClass={
                        RISK_COLORS[p.volatility_level] ?? "bg-gray-100 text-gray-700"
                      }
                    />
                  )}
                </div>

                <div className="mt-3 flex items-center gap-1 text-sm text-gray-500">
                  <Briefcase className="h-3.5 w-3.5" />
                  {formatEnum(p.occupation)}
                </div>

                <p className="mt-2 text-xs text-gray-400">
                  Created {formatDate(p.created_at)}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
