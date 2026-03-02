import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: { value: number; positive: boolean };
  className?: string;
}

export function StatCard({
  label,
  value,
  subtitle,
  icon,
  trend,
  className,
}: StatCardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-gray-200 bg-white p-5 shadow-sm",
        className,
      )}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-gray-500">{label}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {subtitle && (
            <p className="text-xs text-gray-400">{subtitle}</p>
          )}
        </div>
        {icon && (
          <div className="rounded-lg bg-brand-50 p-2.5 text-brand-600">
            {icon}
          </div>
        )}
      </div>
      {trend && (
        <div className="mt-3 flex items-center gap-1 text-xs">
          <span
            className={cn(
              "font-medium",
              trend.positive ? "text-green-600" : "text-red-600",
            )}
          >
            {trend.positive ? "↑" : "↓"} {Math.abs(trend.value)}%
          </span>
          <span className="text-gray-400">vs last period</span>
        </div>
      )}
    </div>
  );
}
