import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  Landmark,
  ShieldAlert,
  TrendingUp,
  AlertTriangle,
  Compass,
  Lock,
  Bot,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/profiles", label: "Profiles", icon: Users },
  { to: "/loans", label: "Loans", icon: Landmark },
  { to: "/risk", label: "Risk", icon: ShieldAlert },
  { to: "/cashflow", label: "Cash Flow", icon: TrendingUp },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle },
  { to: "/guidance", label: "Guidance", icon: Compass },
  { to: "/security", label: "Security", icon: Lock },
  { to: "/advisor", label: "AI Advisor", icon: Bot },
] as const;

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-gray-200 bg-white">
      {/* ── Brand ──────────────────────────────────────────────── */}
      <div className="flex h-16 items-center gap-3 border-b border-gray-200 px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
          <Compass className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-gray-900">Rural Credit</h1>
          <p className="text-[10px] text-gray-400">AI Advisor</p>
        </div>
      </div>

      {/* ── Navigation ─────────────────────────────────────────── */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-50 text-brand-700"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
              )
            }
          >
            <Icon className="h-5 w-5 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* ── Footer ─────────────────────────────────────────────── */}
      <div className="border-t border-gray-200 p-4">
        <p className="text-[10px] text-gray-400 text-center">
          AI for Bharat Hackathon
        </p>
      </div>
    </aside>
  );
}
