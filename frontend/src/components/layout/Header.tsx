import { Bell, Search, LogOut } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useAuth } from "@/features/auth";

const PAGE_TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/profiles": "Borrower Profiles",
  "/loans": "Loan Tracker",
  "/risk": "Risk Assessment",
  "/cashflow": "Cash Flow",
  "/alerts": "Alerts & Scenarios",
  "/guidance": "Credit Guidance",
  "/security": "Security & Privacy",
};

export function Header() {
  const { pathname } = useLocation();
  const { user, logout } = useAuth();
  const baseRoute = "/" + (pathname.split("/")[1] ?? "");
  const title = PAGE_TITLES[baseRoute] ?? "Rural Credit Advisor";

  const initials = user?.full_name
    ?.split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) ?? "?";

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-gray-200 bg-white/80 px-6 backdrop-blur-sm">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>

      <div className="flex items-center gap-4">
        {/* Search (placeholder) */}
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search borrower…"
            className="h-9 w-64 rounded-lg border border-gray-200 bg-gray-50 pl-9 pr-3 text-sm text-gray-600 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>

        {/* Notifications */}
        <button className="relative rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700">
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500" />
        </button>

        {/* User info + logout */}
        <div className="flex items-center gap-3 border-l border-gray-200 pl-4">
          <div className="hidden sm:block text-right">
            <p className="text-sm font-medium text-gray-900">{user?.full_name}</p>
            <p className="text-[10px] text-gray-400">{user?.roles?.[0] ?? "User"}</p>
          </div>
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
            {initials}
          </div>
          <button
            onClick={logout}
            title="Sign out"
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
