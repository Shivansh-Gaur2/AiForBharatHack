import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { loanApi } from "@/api";
import {
  Button,
  Card,
  Badge,
  Input,
  PageSpinner,
  AlertBanner,
  EmptyState,
} from "@/components/ui";
import { formatCurrency, formatDate, formatEnum } from "@/lib/utils";
import { LOAN_STATUS_COLORS } from "@/lib/colors";

export function LoanListPage() {
  const [profileId, setProfileId] = useState("");
  const [searchId, setSearchId] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["loans", searchId],
    queryFn: () => loanApi.listByBorrower(searchId, { limit: 50 }),
    enabled: !!searchId,
  });

  const loans = data?.items ?? [];

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

      {/* Search by profile */}
      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setSearchId(profileId);
          }}
          className="flex gap-3"
        >
          <div className="flex-1">
            <Input
              placeholder="Enter borrower profile ID to view loans…"
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
            />
          </div>
          <Button type="submit" icon={<Search className="h-4 w-4" />}>
            Search
          </Button>
        </form>
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
                      {formatCurrency(loan.terms.principal)} @{" "}
                      {loan.terms.interest_rate_annual}% for{" "}
                      {loan.terms.tenure_months} months
                    </p>
                  </div>
                  <Badge
                    label={loan.status}
                    colorClass={LOAN_STATUS_COLORS[loan.status]}
                  />
                </div>

                <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-gray-400">Outstanding</p>
                    <p className="font-semibold text-gray-900">
                      {formatCurrency(loan.outstanding_balance)}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-400">EMI</p>
                    <p className="font-semibold text-gray-900">
                      {formatCurrency(loan.terms.emi_amount)}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-400">Disbursed</p>
                    <p className="font-semibold text-gray-900">
                      {formatDate(loan.disbursement_date)}
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
