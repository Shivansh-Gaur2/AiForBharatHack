import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { loanApi } from "@/api";
import { Button, Card, CardTitle, Input, Select, AlertBanner } from "@/components/ui";
import { LoanSourceType } from "@/types";
import type { TrackLoanRequest } from "@/types";
import { formatEnum } from "@/lib/utils";

const SOURCE_OPTIONS = Object.values(LoanSourceType).map((v) => ({
  value: v,
  label: formatEnum(v),
}));

export function CreateLoanPage() {
  const navigate = useNavigate();

  const [profileId, setProfileId] = useState("");
  const [lenderName, setLenderName] = useState("");
  const [sourceType, setSourceType] = useState<LoanSourceType>(LoanSourceType.FORMAL);
  const [principal, setPrincipal] = useState("");
  const [rate, setRate] = useState("");
  const [tenure, setTenure] = useState("");
  const [disbursementDate, setDisbursementDate] = useState("");
  const [purpose, setPurpose] = useState("");

  const mutation = useMutation({
    mutationFn: (data: TrackLoanRequest) => loanApi.track(data),
    onSuccess: (loan) => navigate(`/loans/${loan.tracking_id}`),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate({
      profile_id: profileId,
      lender_name: lenderName,
      source_type: sourceType,
      principal_amount: Number(principal),
      interest_rate: Number(rate),
      tenure_months: Number(tenure),
      disbursement_date: disbursementDate,
      purpose: purpose || undefined,
    });
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <Link
        to="/loans"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Loans
      </Link>

      <h2 className="text-xl font-bold text-gray-900">Track New Loan</h2>

      {mutation.isError && (
        <AlertBanner
          variant="error"
          message={
            mutation.error instanceof Error
              ? mutation.error.message
              : "Failed to track loan"
          }
        />
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardTitle className="mb-4">Loan Information</CardTitle>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Input
                label="Borrower Profile ID"
                value={profileId}
                onChange={(e) => setProfileId(e.target.value)}
                required
                placeholder="Enter profile ID"
              />
            </div>
            <Input
              label="Lender Name"
              value={lenderName}
              onChange={(e) => setLenderName(e.target.value)}
              required
              placeholder="e.g., SBI, Local Moneylender"
            />
            <Select
              label="Source Type"
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value as LoanSourceType)}
              options={SOURCE_OPTIONS}
              required
            />
            <Input
              label="Principal Amount (₹)"
              type="number"
              min={0}
              value={principal}
              onChange={(e) => setPrincipal(e.target.value)}
              required
            />
            <Input
              label="Interest Rate (%)"
              type="number"
              min={0}
              max={100}
              step={0.1}
              value={rate}
              onChange={(e) => setRate(e.target.value)}
              required
            />
            <Input
              label="Tenure (months)"
              type="number"
              min={1}
              value={tenure}
              onChange={(e) => setTenure(e.target.value)}
              required
            />
            <Input
              label="Disbursement Date"
              type="date"
              value={disbursementDate}
              onChange={(e) => setDisbursementDate(e.target.value)}
              required
            />
            <div className="sm:col-span-2">
              <Input
                label="Purpose (optional)"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="e.g., Crop cultivation, Equipment purchase"
              />
            </div>
          </div>
        </Card>

        <div className="flex justify-end gap-3">
          <Link to="/loans">
            <Button type="button" variant="outline">
              Cancel
            </Button>
          </Link>
          <Button type="submit" loading={mutation.isPending}>
            Track Loan
          </Button>
        </div>
      </form>
    </div>
  );
}
