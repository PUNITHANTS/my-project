import axios from "axios";

const ACCESS_TOKEN_KEY = "vendor_access_token";
const REFRESH_TOKEN_KEY = "vendor_refresh_token";

// ── Token helpers ────────────────────────────────────────────────────────────

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, access);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function isLoggedIn(): boolean {
  return !!getAccessToken();
}

// ── Axios instance ───────────────────────────────────────────────────────────

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

// Attach bearer token to every request
apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401: try to refresh once, then retry the original request.
// If refresh fails, clear tokens so the app can redirect to login.
let isRefreshing = false;
let pendingQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

function drainQueue(token: string | null, err: unknown) {
  pendingQueue.forEach((p) => (token ? p.resolve(token) : p.reject(err)));
  pendingQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as typeof error.config & { _retry?: boolean };

    // Only intercept 401s that haven't already been retried and are not
    // the refresh endpoint itself (to avoid an infinite loop).
    if (
      error.response?.status !== 401 ||
      original._retry ||
      original.url?.includes("/api/auth/token/")
    ) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      // Another request already kicked off a refresh — queue this one.
      return new Promise((resolve, reject) => {
        pendingQueue.push({
          resolve: (token) => {
            original.headers.Authorization = `Bearer ${token}`;
            resolve(apiClient(original));
          },
          reject,
        });
      });
    }

    original._retry = true;
    isRefreshing = true;

    try {
      const refresh = getRefreshToken();
      if (!refresh) throw new Error("No refresh token");

      const { data } = await axios.post<{ access: string }>(
        `${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}/api/auth/token/refresh/`,
        { refresh },
      );

      setTokens(data.access, refresh);
      apiClient.defaults.headers.common.Authorization = `Bearer ${data.access}`;
      drainQueue(data.access, null);
      original.headers.Authorization = `Bearer ${data.access}`;
      return apiClient(original);
    } catch (refreshError) {
      drainQueue(null, refreshError);
      clearTokens();
      // Dispatch a custom event so App.tsx can react and show the login screen
      // without a hard page reload.
      window.dispatchEvent(new Event("vendor:session-expired"));
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

export default apiClient;
