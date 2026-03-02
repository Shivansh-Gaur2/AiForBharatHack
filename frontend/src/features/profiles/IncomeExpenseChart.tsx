import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardTitle } from "@/components/ui";
import { getMonthName, formatCurrency } from "@/lib/utils";
import type { IncomeRecord, ExpenseRecord } from "@/types";

interface Props {
  incomeRecords: IncomeRecord[];
  expenseRecords: ExpenseRecord[];
}

export function IncomeExpenseChart({ incomeRecords, expenseRecords }: Props) {
  const chartData = useMemo(() => {
    const buckets = new Map<string, { income: number; expense: number }>();

    for (const r of incomeRecords) {
      const key = `${r.year}-${String(r.month).padStart(2, "0")}`;
      const entry = buckets.get(key) ?? { income: 0, expense: 0 };
      entry.income += r.amount;
      buckets.set(key, entry);
    }
    for (const r of expenseRecords) {
      const key = `${r.year}-${String(r.month).padStart(2, "0")}`;
      const entry = buckets.get(key) ?? { income: 0, expense: 0 };
      entry.expense += r.amount;
      buckets.set(key, entry);
    }

    return Array.from(buckets.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, val]) => {
        const [year, month] = key.split("-");
        return {
          name: `${getMonthName(Number(month))} ${year?.slice(2)}`,
          Income: val.income,
          Expenses: val.expense,
        };
      });
  }, [incomeRecords, expenseRecords]);

  if (chartData.length === 0) {
    return (
      <Card>
        <CardTitle>Income vs Expenses</CardTitle>
        <p className="mt-4 text-sm text-gray-400">
          No income or expense records to display.
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <CardTitle className="mb-4">Income vs Expenses</CardTitle>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} barCategoryGap="20%">
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip
              formatter={(v: number) => formatCurrency(v)}
              contentStyle={{
                borderRadius: 8,
                border: "1px solid #e5e7eb",
                fontSize: 12,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="Income" fill="#22c55e" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Expenses" fill="#ef4444" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
