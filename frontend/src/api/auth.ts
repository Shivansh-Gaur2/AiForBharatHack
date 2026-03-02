import { httpClient } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AuthUser {
  user_id: string;
  email: string;
  full_name: string;
  roles: string[];
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface AuthResponse {
  user: AuthUser;
  token: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  roles?: string[];
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

const BASE = "/api/v1/auth";

export const authApi = {
  login: (data: LoginRequest) =>
    httpClient.post<AuthResponse>(`${BASE}/login`, data).then((r) => r.data),

  register: (data: RegisterRequest) =>
    httpClient
      .post<AuthResponse>(`${BASE}/register`, data)
      .then((r) => r.data),

  validate: (token: string) =>
    httpClient
      .post<{ valid: boolean; user_id: string | null; email: string | null; roles: string[] }>(
        `${BASE}/validate`,
        { token },
      )
      .then((r) => r.data),
};
