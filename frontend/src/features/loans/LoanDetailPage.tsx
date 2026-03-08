import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Calendar, Percent, Clock, IndianRupee } from "lucide-react";
import { loanApi } from "@/api";
import {
  Card,
  CardTitle,
  Badge,
  StatCard,
  PageSpinner,
  AlertBanner,
} from "@/components/ui";
import { formatCurrency, formatDate, formatEnum, formatPercent } from "@/lib/utils";
import { LOAN_STATUS_COLORS } from "@/lib/colors";

export function LoanDetailPage() {
  const { trackingId } = useParams<{ trackingId: string }>();

  const { data: loan, isLoading, error } = useQuery({
    queryKey: ["loan", trackingId],
    queryFn: () => loanApi.get(trackingId!),
    enabled: !!trackingId,
  });

  if (isLoading) return <PageSpinner />;
  if (error || !loan)
    return (
      <AlertBanner
        variant="error"
        message={error instanceof Error ? error.message : "Loan not found"}
      />
    );

  const repaidPct =
    loan.terms.principal > 0
      ? loan.total_repaid / loan.terms.principal
      : 0;

  return (
    <div className="space-y-6">
      <Link
        to="/loans"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Loans
      </Link>

      <Card>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              {loan.lender_name}
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              {formatEnum(loan.source_type)} Loan · Tracking ID:{" "}
              <span className="font-mono">{loan.tracking_id.slice(0, 8)}…</span>
            </p>
          </div>
          <Badge
            label={loan.status}
            colorClass={LOAN_STATUS_COLORS[loan.status]}
          />
        </div>
      </Card>

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Principal"
          value={formatCurrency(loan.terms.principal)}
          icon={<IndianRupee className="h-5 w-5" />}
        />
        <StatCard
          label="Outstanding"
          value={formatCurrency(loan.outstanding_balance)}
          subtitle={`${formatPercent(1 - repaidPct)} remaining`}
        />
        <StatCard
          label="Interest Rate"
          value={`${loan.terms.interest_rate_annual}%`}
          icon={<Percent className="h-5 w-5" />}
        />
        <StatCard
          label="Monthly EMI"
          value={formatCurrency(loan.terms.emi_amount)}
          icon={<Clock className="h-5 w-5" />}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Loan details */}
        <Card>
          <CardTitle className="mb-4">Loan Details</CardTitle>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Tenure</dt>
              <dd className="font-medium">{loan.terms.tenure_months} months</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Disbursement Date</dt>
              <dd className="font-medium flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5 text-gray-400" />
                {formatDate(loan.disbursement_date)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Maturity Date</dt>
              <dd className="font-medium flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5 text-gray-400" />
                {formatDate(loan.maturity_date)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Total Repaid</dt>
              <dd className="font-medium text-green-600">
                {formatCurrency(loan.total_repaid)}
              </dd>
            </div>
          </dl>

          {/* Repayment progress */}
          <div className="mt-6">
            <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
              <span>Repayment Progress</span>
              <span>{formatPercent(repaidPct)}</span>
            </div>
            <div className="h-2.5 rounded-full bg-gray-100">
              <div
                className="h-2.5 rounded-full bg-brand-500 transition-all"
                style={{ width: `${repaidPct * 100}%` }}
              />
            </div>
          </div>
        </Card>

        {/* Repayment history */}
        <Card>
          <CardTitle className="mb-4">Repayment History</CardTitle>
          {loan.repayments.length === 0 ? (
            <p className="text-sm text-gray-400">No repayments recorded yet.</p>
          ) : (
            <div className="max-h-80 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b border-gray-100 text-left text-xs text-gray-400">
                    <th className="pb-2">Date</th>
                    <th className="pb-2 text-right">Amount</th>
                    <th className="pb-2 text-right">Status</th>
                    <th className="pb-2 text-right">Days Overdue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {loan.repayments.map((r, i) => (
                    <tr key={i}>
                      <td className="py-2 text-gray-700">
                        {formatDate(r.date)}
                      </td>
                      <td className="py-2 text-right font-medium">
                        {formatCurrency(r.amount)}
                      </td>
                      <td className="py-2 text-right">
                        <span className={r.is_late ? "text-red-500" : "text-green-600"}>
                          {r.is_late ? "Late" : "On time"}
                        </span>
                      </td>
                      <td className="py-2 text-right text-gray-500">
                        {r.days_overdue > 0 ? `${r.days_overdue}d` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
