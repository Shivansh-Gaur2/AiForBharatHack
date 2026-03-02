import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { PageSpinner } from "@/components/ui";

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRoles?: string[];
}

/**
 * Route guard — redirects to /login if the user is not authenticated.
 * Optionally enforces role-based access.
 */
export function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <PageSpinner />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredRoles && requiredRoles.length > 0 && user) {
    const hasRole = requiredRoles.some((role) => user.roles.includes(role));
    if (!hasRole) {
      return (
        <div className="flex h-96 items-center justify-center">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900">403</h2>
            <p className="mt-1 text-sm text-gray-500">
              Insufficient permissions. Required role:{" "}
              {requiredRoles.join(", ")}
            </p>
          </div>
        </div>
      );
    }
  }

  return <>{children}</>;
}
