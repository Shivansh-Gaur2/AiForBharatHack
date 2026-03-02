import axios from "axios";

/** Shared Axios instance — all service-specific clients derive from this. */
export const httpClient = axios.create({
  timeout: 15_000,
  headers: { "Content-Type": "application/json" },
});

// ─── Response interceptor: unwrap data, normalise errors ────────────────────

httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error)) {
      const message =
        error.response?.data?.detail ??
        error.response?.data?.message ??
        error.message;
      return Promise.reject(new ApiError(message, error.response?.status));
    }
    return Promise.reject(error);
  },
);

// ─── Typed API error ────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
