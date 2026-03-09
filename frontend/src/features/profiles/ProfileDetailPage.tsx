import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  MapPin,
  Phone,
  Calendar,
  Briefcase,
  TrendingUp,
  Wheat,
  Trash2,
} from "lucide-react";
import { profileApi } from "@/api";
import {
  Button,
  Card,
  CardTitle,
  Badge,
  PageSpinner,
  AlertBanner,
  StatCard,
} from "@/components/ui";
import { formatCurrency, formatDate, formatEnum, formatPercent } from "@/lib/utils";
import { IncomeExpenseChart } from "./IncomeExpenseChart";
import { VolatilityCard } from "./VolatilityCard";

export function ProfileDetailPage() {
  const { profileId: id } = useParams<{ profileId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => profileApi.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      navigate("/profiles");
    },
  });

  const handleDelete = () => {
    if (window.confirm("Delete this profile permanently? This cannot be undone.")) {
      deleteMutation.mutate();
    }
  };

  const { data: profile, isLoading, error } = useQuery({
    queryKey: ["profile", id],
    queryFn: () => profileApi.get(id!),
    enabled: !!id,
  });

  if (isLoading) return <PageSpinner />;
  if (error || !profile)
    return (
      <AlertBanner
        variant="error"
        message={error instanceof Error ? error.message : "Profile not found"}
      />
    );

  const pi = profile.personal_info;
  const li = profile.livelihood_info;
  const totalIncome = profile.income_records.reduce((s, r) => s + r.amount, 0) || profile.estimated_annual_income;
  const totalExpense = profile.expense_records.reduce((s, r) => s + r.amount, 0) || (profile.average_monthly_expense * 12);
  const hasIncomeRecords = profile.income_records.length > 0;

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        to="/profiles"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Profiles
      </Link>

      {/* Profile header card */}
      <Card>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{pi.name}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
              <span className="flex items-center gap-1">
                <MapPin className="h-4 w-4" />
                {pi.location}, {pi.district}, {pi.state}
              </span>
              {pi.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="h-4 w-4" />
                  {pi.phone}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                Age {pi.age}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            <Link to={`/risk?profile=${id}`}>
              <Button variant="outline" size="sm">
                Assess Risk
              </Button>
            </Link>
            <Link to={`/guidance?profile=${id}`}>
              <Button size="sm">Get Guidance</Button>
            </Link>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="text-red-600 border-red-300 hover:bg-red-50"
            >
              <Trash2 className="h-4 w-4 mr-1" />
              {deleteMutation.isPending ? "Deleting…" : "Delete"}
            </Button>
          </div>
        </div>
      </Card>

      {/* KPI row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label={hasIncomeRecords ? "Total Income" : "Est. Annual Income"}
          value={formatCurrency(totalIncome)}
          subtitle={hasIncomeRecords ? `${profile.income_records.length} records` : "from crop estimates"}
          icon={<TrendingUp className="h-5 w-5" />}
        />
        <StatCard
          label="Total Expenses"
          value={formatCurrency(totalExpense)}
          subtitle={profile.expense_records.length > 0 ? `${profile.expense_records.length} records` : "estimated"}
        />
        <StatCard
          label="Monthly Surplus"
          value={formatCurrency(profile.monthly_surplus)}
          subtitle={`Avg income: ${formatCurrency(profile.average_monthly_income)}/mo`}
        />
        <StatCard
          label="Primary Occupation"
          value={formatEnum(li.primary_occupation)}
          icon={<Briefcase className="h-5 w-5" />}
        />
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column — charts */}
        <div className="space-y-6 lg:col-span-2">
          <IncomeExpenseChart
            incomeRecords={profile.income_records}
            expenseRecords={profile.expense_records}
          />
        </div>

        {/* Right column — details */}
        <div className="space-y-6">
          {profile.volatility_metrics && (
            <VolatilityCard metrics={profile.volatility_metrics} />
          )}

          {/* Livelihood details */}
          <Card>
            <CardTitle className="mb-4">Livelihood Details</CardTitle>
            <dl className="space-y-3 text-sm">
              {li.land_details && (
                <>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Owned Land</dt>
                    <dd className="font-medium">{li.land_details.owned_acres} acres</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Leased Land</dt>
                    <dd className="font-medium">{li.land_details.leased_acres} acres</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Irrigated</dt>
                    <dd className="font-medium">
                      {formatPercent(li.land_details.irrigated_percentage / 100)}
                    </dd>
                  </div>
                </>
              )}
              {li.crops.length > 0 && (
                <div className="pt-2 border-t border-gray-100">
                  <dt className="text-gray-500 mb-2 flex items-center gap-1">
                    <Wheat className="h-4 w-4" /> Crops
                  </dt>
                  <dd className="flex flex-wrap gap-1.5">
                    {li.crops.map((c, i) => (
                      <Badge key={i} label={c.crop_name} colorClass="bg-green-50 text-green-700" />
                    ))}
                  </dd>
                </div>
              )}
              {li.secondary_occupations.length > 0 && (
                <div className="pt-2 border-t border-gray-100">
                  <dt className="text-gray-500 mb-2">Secondary Occupations</dt>
                  <dd className="flex flex-wrap gap-1.5">
                    {li.secondary_occupations.map((o) => (
                      <Badge key={o} label={o} />
                    ))}
                  </dd>
                </div>
              )}
            </dl>
          </Card>

          {/* Seasonal factors */}
          {profile.seasonal_factors.length > 0 && (
            <Card>
              <CardTitle className="mb-4">Seasonal Factors</CardTitle>
              <div className="space-y-3">
                {profile.seasonal_factors.map((sf, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-gray-100 p-3"
                  >
                    <div className="flex items-center justify-between">
                      <Badge label={sf.season} colorClass="bg-earth-100 text-earth-700" />
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      {sf.description}
                    </p>
                    <div className="mt-2 flex gap-4 text-xs">
                      <span className="text-green-600">
                        Income ×{sf.income_multiplier.toFixed(1)}
                      </span>
                      <span className="text-red-600">
                        Expense ×{sf.expense_multiplier.toFixed(1)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Metadata */}
          <Card>
            <dl className="space-y-2 text-xs text-gray-400">
              <div className="flex justify-between">
                <dt>Profile ID</dt>
                <dd className="font-mono">{profile.profile_id.slice(0, 8)}…</dd>
              </div>
              <div className="flex justify-between">
                <dt>Created</dt>
                <dd>{formatDate(profile.created_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Updated</dt>
                <dd>{formatDate(profile.updated_at)}</dd>
              </div>
            </dl>
          </Card>
        </div>
      </div>
    </div>
  );
}
