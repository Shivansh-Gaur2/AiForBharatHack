import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { Button, Input, AlertBanner } from "@/components/ui";
import { Compass } from "lucide-react";

type Mode = "login" | "register";

export function LoginPage() {
  const { isAuthenticated, login, register, isLoading } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: Location })?.from?.pathname ?? "/";

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // If already authenticated, redirect to the intended page
  if (isAuthenticated && !isLoading) {
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      if (mode === "login") {
        await login({ email, password });
      } else {
        if (!fullName.trim()) {
          setError("Full name is required");
          setSubmitting(false);
          return;
        }
        await register({ email, password, full_name: fullName });
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Authentication failed",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 px-4">
      <div className="w-full max-w-md">
        {/* Brand header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-brand-600 text-white shadow-lg">
            <Compass className="h-8 w-8" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            Rural Credit Advisor
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            AI-powered credit decision support for rural India
          </p>
        </div>

        {/* Auth card */}
        <div className="rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
          <h2 className="mb-6 text-lg font-semibold text-gray-900">
            {mode === "login" ? "Sign in to your account" : "Create an account"}
          </h2>

          {error && <AlertBanner variant="error" message={error} className="mb-4" />}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <Input
                label="Full Name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g., Ramesh Kumar"
                required
                autoComplete="name"
              />
            )}

            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="email"
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              hint={mode === "register" ? "Minimum 6 characters" : undefined}
            />

            <Button
              type="submit"
              className="w-full"
              loading={submitting}
              size="lg"
            >
              {mode === "login" ? "Sign In" : "Create Account"}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-gray-500">
            {mode === "login" ? (
              <>
                Don't have an account?{" "}
                <button
                  type="button"
                  onClick={() => { setMode("register"); setError(""); }}
                  className="font-medium text-brand-600 hover:text-brand-700"
                >
                  Register
                </button>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => { setMode("login"); setError(""); }}
                  className="font-medium text-brand-600 hover:text-brand-700"
                >
                  Sign in
                </button>
              </>
            )}
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-gray-400">
          AI for Bharat Hackathon &middot; Rural Credit Advisory System
        </p>
      </div>
    </div>
  );
}
