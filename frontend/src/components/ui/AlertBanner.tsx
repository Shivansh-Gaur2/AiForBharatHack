import { AlertCircle, CheckCircle, Info, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type AlertVariant = "info" | "success" | "warning" | "error";

interface AlertBannerProps {
  variant?: AlertVariant;
  title?: string;
  message: string;
  className?: string;
}

const styles: Record<AlertVariant, { bg: string; icon: React.ReactNode }> = {
  info: {
    bg: "bg-blue-50 border-blue-200 text-blue-800",
    icon: <Info className="h-5 w-5 text-blue-500" />,
  },
  success: {
    bg: "bg-green-50 border-green-200 text-green-800",
    icon: <CheckCircle className="h-5 w-5 text-green-500" />,
  },
  warning: {
    bg: "bg-yellow-50 border-yellow-200 text-yellow-800",
    icon: <AlertCircle className="h-5 w-5 text-yellow-500" />,
  },
  error: {
    bg: "bg-red-50 border-red-200 text-red-800",
    icon: <XCircle className="h-5 w-5 text-red-500" />,
  },
};

export function AlertBanner({
  variant = "info",
  title,
  message,
  className,
}: AlertBannerProps) {
  const { bg, icon } = styles[variant];
  return (
    <div
      role="alert"
      className={cn("flex gap-3 rounded-lg border p-4", bg, className)}
    >
      <div className="flex-shrink-0 pt-0.5">{icon}</div>
      <div>
        {title && <p className="font-medium">{title}</p>}
        <p className="text-sm">{message}</p>
      </div>
    </div>
  );
}
