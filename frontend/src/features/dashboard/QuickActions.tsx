import { Link } from "react-router-dom";
import {
  UserPlus,
  Landmark,
  ShieldAlert,
  Compass,
} from "lucide-react";
import { Card, CardTitle } from "@/components/ui";

const ACTIONS = [
  { label: "New Profile", to: "/profiles/new", icon: UserPlus, color: "bg-blue-50 text-blue-600" },
  { label: "Track Loan", to: "/loans/new", icon: Landmark, color: "bg-green-50 text-green-600" },
  { label: "Assess Risk", to: "/risk", icon: ShieldAlert, color: "bg-orange-50 text-orange-600" },
  { label: "Get Guidance", to: "/guidance", icon: Compass, color: "bg-purple-50 text-purple-600" },
] as const;

export function QuickActions() {
  return (
    <Card>
      <CardTitle className="mb-4">Quick Actions</CardTitle>
      <div className="grid grid-cols-2 gap-3">
        {ACTIONS.map(({ label, to, icon: Icon, color }) => (
          <Link
            key={to}
            to={to}
            className="flex flex-col items-center gap-2 rounded-lg border border-gray-100 p-4 text-center transition-colors hover:border-gray-200 hover:bg-gray-50"
          >
            <div className={`rounded-lg p-2 ${color}`}>
              <Icon className="h-5 w-5" />
            </div>
            <span className="text-xs font-medium text-gray-700">{label}</span>
          </Link>
        ))}
      </div>
    </Card>
  );
}
