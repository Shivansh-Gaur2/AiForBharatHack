import { cn } from "@/lib/utils";
import { formatEnum } from "@/lib/utils";

interface BadgeProps {
  label: string;
  colorClass?: string;
  className?: string;
}

/** Generic badge component — pass a Tailwind color class or use the default gray. */
export function Badge({ label, colorClass, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        colorClass ?? "bg-gray-100 text-gray-800",
        className,
      )}
    >
      {formatEnum(label)}
    </span>
  );
}
