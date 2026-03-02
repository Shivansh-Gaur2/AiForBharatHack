import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import { authApi, type AuthUser, type LoginRequest, type RegisterRequest } from "@/api/auth";
import { httpClient } from "@/api/client";

// ---------------------------------------------------------------------------
// Storage keys
// ---------------------------------------------------------------------------
const TOKEN_KEY = "rca_token";
const USER_KEY = "rca_user";

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------
interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      const stored = localStorage.getItem(USER_KEY);
      return stored ? (JSON.parse(stored) as AuthUser) : null;
    } catch {
      return null;
    }
  });

  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem(TOKEN_KEY),
  );

  const [isLoading, setIsLoading] = useState(true);

  // ── Attach / detach auth header on token changes ────────────────────
  useEffect(() => {
    if (token) {
      httpClient.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    } else {
      delete httpClient.defaults.headers.common["Authorization"];
    }
  }, [token]);

  // ── Validate persisted token on mount ───────────────────────────────
  useEffect(() => {
    async function validateStoredToken() {
      if (!token) {
        setIsLoading(false);
        return;
      }
      try {
        const result = await authApi.validate(token);
        if (!result.valid) {
          // Token expired or invalid — clear session
          handleLogout();
        }
      } catch {
        // Backend unreachable — keep session (work offline)
      } finally {
        setIsLoading(false);
      }
    }
    validateStoredToken();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 401 interceptor — auto-logout on expired tokens ─────────────────
  useEffect(() => {
    const id = httpClient.interceptors.response.use(
      (res) => res,
      (err) => {
        if (err?.response?.status === 401 && token) {
          handleLogout();
        }
        return Promise.reject(err);
      },
    );
    return () => httpClient.interceptors.response.eject(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const persistSession = useCallback((u: AuthUser, t: string) => {
    localStorage.setItem(TOKEN_KEY, t);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    setUser(u);
    setToken(t);
  }, []);

  const handleLogout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
    setToken(null);
  }, []);

  const login = useCallback(
    async (data: LoginRequest) => {
      const res = await authApi.login(data);
      persistSession(res.user, res.token);
    },
    [persistSession],
  );

  const register = useCallback(
    async (data: RegisterRequest) => {
      const res = await authApi.register(data);
      persistSession(res.user, res.token);
    },
    [persistSession],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: !!user && !!token,
      isLoading,
      login,
      register,
      logout: handleLogout,
    }),
    [user, token, isLoading, login, register, handleLogout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
