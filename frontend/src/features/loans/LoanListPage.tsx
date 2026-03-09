import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, Search, User, ChevronDown } from "lucide-react";
import { loanApi, profileApi } from "@/api";
import {
  Button,
  Card,
  Badge,
  Input,
  PageSpinner,
  AlertBanner,
  EmptyState,
} from "@/components/ui";
import { formatCurrency, formatEnum } from "@/lib/utils";
import { LOAN_STATUS_COLORS } from "@/lib/colors";

export function LoanListPage() {
  const [profileId, setProfileId] = useState("");
  const [searchId, setSearchId] = useState("");

  // Fetch all profiles for the dropdown
  const { data: profilesData, isLoading: profilesLoading } = useQuery({
    queryKey: ["profiles-list"],
    queryFn: () => profileApi.list({ limit: 100 }),
  });
  const profiles = profilesData?.items ?? [];

  const { data, isLoading, error } = useQuery({
    queryKey: ["loans", searchId],
    queryFn: () => loanApi.listByBorrower(searchId, { limit: 50 }),
    enabled: !!searchId,
  });

  const loans = data?.items ?? [];

  // Auto-select the first profile once profiles load if nothing is selected
  useEffect(() => {
    if (profiles.length > 0 && !profileId && !searchId) {
      setProfileId(profiles[0]!.profile_id);
      setSearchId(profiles[0]!.profile_id);
    }
  }, [profiles]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Loan Tracker</h2>
          <p className="text-sm text-gray-500">
            Track and manage borrower loans across all sources
          </p>
        </div>
        <Link to="/loans/new">
          <Button icon={<Plus className="h-4 w-4" />}>Track Loan</Button>
        </Link>
      </div>

      {/* Profile selector */}
      <Card>
        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-700">
            <User className="inline h-4 w-4 mr-1 -mt-0.5" />
            Select Borrower
          </label>

          {profilesLoading ? (
            <div className="text-sm text-gray-400">Loading profiles…</div>
          ) : profiles.length > 0 ? (
            <div className="flex gap-3">
              <div className="relative flex-1">
                <select
                  value={profileId}
                  onChange={(e) => {
                    setProfileId(e.target.value);
                    setSearchId(e.target.value);
                  }}
                  className="w-full appearance-none rounded-lg border border-gray-300 bg-white px-3 py-2 pr-10 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="" disabled>
                    Choose a borrower…
                  </option>
                  {profiles.map((p) => (
                    <option key={p.profile_id} value={p.profile_id}>
                      {p.name} — {p.location} ({p.occupation})
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              </div>
            </div>
          ) : (
            /* Fallback to manual ID entry if no profiles exist */
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setSearchId(profileId);
              }}
              className="flex gap-3"
            >
              <div className="flex-1">
                <Input
                  placeholder="Enter borrower profile ID…"
                  value={profileId}
                  onChange={(e) => setProfileId(e.target.value)}
                />
              </div>
              <Button type="submit" icon={<Search className="h-4 w-4" />}>
                Search
              </Button>
            </form>
          )}
        </div>
      </Card>

      {/* Results */}
      {isLoading && <PageSpinner />}
      {error && (
        <AlertBanner
          variant="error"
          message={error instanceof Error ? error.message : "Failed to load loans"}
        />
      )}

      {searchId && !isLoading && loans.length === 0 && (
        <EmptyState
          title="No loans found"
          description="No loans tracked for this borrower profile."
        />
      )}

      {loans.length > 0 && (
        <div className="space-y-3">
          {loans.map((loan) => (
            <Link key={loan.tracking_id} to={`/loans/${loan.tracking_id}`}>
              <Card className="transition-shadow hover:shadow-md cursor-pointer mb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">
                      {loan.lender_name}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {formatEnum(loan.source_type)} ·{" "}
                      {formatCurrency(loan.principal)}
                    </p>
                  </div>
                  <Badge
                    label={loan.status}
                    colorClass={LOAN_STATUS_COLORS[loan.status]}
                  />
                </div>

                <div className="mt-3 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-gray-400">Outstanding</p>
                    <p className="font-semibold text-gray-900">
                      {formatCurrency(loan.outstanding_balance)}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-400">Monthly EMI</p>
                    <p className="font-semibold text-gray-900">
                      {formatCurrency(loan.monthly_obligation)}
                    </p>
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
