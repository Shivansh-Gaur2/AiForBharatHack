import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, User } from "lucide-react";
import { loanApi, profileApi } from "@/api";
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

  const { data: profilesData, isLoading: loadingProfiles } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => profileApi.list({ limit: 200 }),
  });
  const profiles = profilesData?.items ?? [];
  const selectedProfile = profiles.find((p) => p.profile_id === profileId);
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

  // ── Compute EMI: P × r × (1+r)^n / ((1+r)^n − 1) ──
  function computeEmi(p: number, annualRate: number, months: number): number {
    if (p <= 0 || months <= 0) return 0;
    if (annualRate <= 0) return Math.round(p / months);
    const r = annualRate / 100 / 12;
    const factor = Math.pow(1 + r, months);
    return Math.round((p * r * factor) / (factor - 1));
  }

  const emiAmount = computeEmi(Number(principal), Number(rate), Number(tenure));

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate({
      profile_id: profileId,
      lender_name: lenderName,
      source_type: sourceType,
      terms: {
        principal: Number(principal),
        interest_rate_annual: Number(rate),
        tenure_months: Number(tenure),
        emi_amount: emiAmount,
      },
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
              <Select
                label="Borrower Profile"
                value={profileId}
                onChange={(e) => setProfileId(e.target.value)}
                options={
                  loadingProfiles
                    ? [{ value: "", label: "Loading profiles…" }]
                    : profiles.map((p) => ({
                        value: p.profile_id,
                        label: `${p.name} — ${p.location}`,
                      }))
                }
                required
              />
              {selectedProfile && (
                <div className="mt-2 flex items-center gap-2 rounded-lg bg-brand-50 border border-brand-200 px-3 py-2">
                  <User className="h-4 w-4 text-brand-600" />
                  <span className="text-sm font-medium text-brand-700">{selectedProfile.name}</span>
                  <span className="text-xs text-brand-500">{selectedProfile.location}</span>
                </div>
              )}
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

            {emiAmount > 0 && (
              <div className="sm:col-span-2 rounded-lg bg-brand-50 border border-brand-200 px-4 py-3">
                <p className="text-sm text-brand-700">
                  Estimated Monthly EMI:{" "}
                  <span className="font-semibold">₹{emiAmount.toLocaleString("en-IN")}</span>
                </p>
              </div>
            )}
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
