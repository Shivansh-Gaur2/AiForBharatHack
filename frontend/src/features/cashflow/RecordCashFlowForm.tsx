import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { cashflowApi } from "@/api";
import {
  Button,
  Card,
  CardTitle,
  Input,
  Select,
  AlertBanner,
} from "@/components/ui";
import { CashFlowCategory, FlowDirection } from "@/types";
import { formatEnum } from "@/lib/utils";

// ─── Category options split by direction ────────────────────────────────────

const INFLOW_CATEGORIES = [
  CashFlowCategory.CROP_INCOME,
  CashFlowCategory.LIVESTOCK_INCOME,
  CashFlowCategory.LABOUR_INCOME,
  CashFlowCategory.REMITTANCE,
  CashFlowCategory.GOVERNMENT_SUBSIDY,
  CashFlowCategory.OTHER_INCOME,
];

const OUTFLOW_CATEGORIES = [
  CashFlowCategory.SEED_FERTILIZER,
  CashFlowCategory.LABOUR_EXPENSE,
  CashFlowCategory.EQUIPMENT,
  CashFlowCategory.HOUSEHOLD,
  CashFlowCategory.EDUCATION,
  CashFlowCategory.HEALTHCARE,
  CashFlowCategory.LOAN_REPAYMENT,
  CashFlowCategory.OTHER_EXPENSE,
];

const MONTH_OPTIONS = Array.from({ length: 12 }, (_, i) => ({
  value: String(i + 1),
  label: new Date(2000, i).toLocaleString("en", { month: "long" }),
}));

const currentYear = new Date().getFullYear();
const YEAR_OPTIONS = Array.from({ length: 5 }, (_, i) => ({
  value: String(currentYear - 2 + i),
  label: String(currentYear - 2 + i),
}));

interface RecordRow {
  id: number;
  direction: FlowDirection;
  category: string;
  amount: string;
  month: string;
  year: string;
}

function emptyRow(id: number): RecordRow {
  return {
    id,
    direction: FlowDirection.INFLOW,
    category: "",
    amount: "",
    month: String(new Date().getMonth() + 1),
    year: String(currentYear),
  };
}

interface Props {
  profileId: string;
}

export function RecordCashFlowForm({ profileId }: Props) {
  const queryClient = useQueryClient();
  const [rows, setRows] = useState<RecordRow[]>([emptyRow(1)]);
  const [nextId, setNextId] = useState(2);
  const [success, setSuccess] = useState(false);

  const mutation = useMutation({
    mutationFn: async () => {
      const promises = rows.map((r) =>
        cashflowApi.recordCashFlow({
          profile_id: profileId,
          direction: r.direction,
          category: r.category as CashFlowCategory,
          amount: Number(r.amount),
          month: Number(r.month),
          year: Number(r.year),
        }),
      );
      return Promise.all(promises);
    },
    onSuccess: () => {
      setSuccess(true);
      setRows([emptyRow(nextId)]);
      setNextId(nextId + 1);
      queryClient.invalidateQueries({ queryKey: ["cashflow-forecast", profileId] });
      queryClient.invalidateQueries({ queryKey: ["cashflow-records", profileId] });
      setTimeout(() => setSuccess(false), 4000);
    },
  });

  function addRow() {
    setRows((prev) => [...prev, emptyRow(nextId)]);
    setNextId((n) => n + 1);
  }

  function removeRow(id: number) {
    setRows((prev) => (prev.length === 1 ? prev : prev.filter((r) => r.id !== id)));
  }

  function updateRow(id: number, field: keyof RecordRow, value: string) {
    setRows((prev) =>
      prev.map((r) => {
        if (r.id !== id) return r;
        const updated = { ...r, [field]: value };
        // Reset category when direction changes
        if (field === "direction") updated.category = "";
        return updated;
      }),
    );
  }

  const isValid = rows.every(
    (r) => r.category && Number(r.amount) > 0 && r.month && r.year,
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (isValid) mutation.mutate();
  }

  return (
    <Card>
      <CardTitle className="mb-4">Record Cash Flow</CardTitle>
      <form onSubmit={handleSubmit} className="space-y-4">
        {rows.map((row, idx) => {
          const categories =
            row.direction === FlowDirection.INFLOW
              ? INFLOW_CATEGORIES
              : OUTFLOW_CATEGORIES;

          return (
            <div
              key={row.id}
              className="rounded-lg border border-gray-100 bg-gray-50/50 p-3 space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-gray-500">
                  Entry {idx + 1}
                </span>
                {rows.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeRow(row.id)}
                    className="text-gray-400 hover:text-red-500 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Select
                  label="Type"
                  value={row.direction}
                  onChange={(e) =>
                    updateRow(row.id, "direction", e.target.value)
                  }
                  options={[
                    { value: FlowDirection.INFLOW, label: "Income (Inflow)" },
                    { value: FlowDirection.OUTFLOW, label: "Expense (Outflow)" },
                  ]}
                />
                <Select
                  label="Category"
                  value={row.category}
                  onChange={(e) =>
                    updateRow(row.id, "category", e.target.value)
                  }
                  options={categories.map((c) => ({
                    value: c,
                    label: formatEnum(c),
                  }))}
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <Input
                  label="Amount (₹)"
                  type="number"
                  min={1}
                  step={100}
                  value={row.amount}
                  onChange={(e) =>
                    updateRow(row.id, "amount", e.target.value)
                  }
                  placeholder="e.g. 12000"
                />
                <Select
                  label="Month"
                  value={row.month}
                  onChange={(e) =>
                    updateRow(row.id, "month", e.target.value)
                  }
                  options={MONTH_OPTIONS}
                />
                <Select
                  label="Year"
                  value={row.year}
                  onChange={(e) =>
                    updateRow(row.id, "year", e.target.value)
                  }
                  options={YEAR_OPTIONS}
                />
              </div>
            </div>
          );
        })}

        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={addRow}
            icon={<Plus className="h-4 w-4" />}
          >
            Add Entry
          </Button>
          <Button
            type="submit"
            loading={mutation.isPending}
            disabled={!isValid}
          >
            Save {rows.length > 1 ? `${rows.length} Records` : "Record"}
          </Button>
        </div>

        {mutation.isError && (
          <AlertBanner
            variant="error"
            message={
              mutation.error instanceof Error
                ? mutation.error.message
                : "Failed to save records"
            }
          />
        )}
        {success && (
          <AlertBanner
            variant="success"
            message={`${rows.length === 1 ? "Record" : "Records"} saved successfully! You can now generate/refresh the forecast.`}
          />
        )}
      </form>
    </Card>
  );
}
