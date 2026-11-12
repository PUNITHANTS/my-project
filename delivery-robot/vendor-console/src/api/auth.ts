import axios from "axios";
import { clearTokens, setTokens } from "./client";

interface TokenResponse {
  access: string;
  refresh: string;
}

/**
 * POST /api/auth/token/
 * On success stores both tokens and returns true.
 * On bad credentials (400/401) returns false.
 * Throws on unexpected network/server errors.
 */
export async function login(username: string, password: string): Promise<boolean> {
  try {
    const { data } = await axios.post<TokenResponse>(
      `${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}/api/auth/token/`,
      { username, password },
    );
    setTokens(data.access, data.refresh);
    return true;
  } catch (err) {
    if (axios.isAxiosError(err) && (err.response?.status === 400 || err.response?.status === 401)) {
      return false;
    }
    throw err;
  }
}

/**
 * Clears both tokens from localStorage, effectively ending the session.
 */
export function logout(): void {
  clearTokens();
}

export interface RegisterPayload {
  username: string;
  password: string;
  confirm_password: string;
  vendor_name: string;
  phone?: string;
  address?: string;
}

/**
 * POST /api/accounts/register/
 * Creates a vendor user + vendor record. Returns true on success.
 * Returns a validation error message string on 400, throws on server errors.
 */
export async function register(payload: RegisterPayload): Promise<true | string> {
  try {
    await axios.post(
      `${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}/api/accounts/register/`,
      payload,
    );
    return true;
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 400) {
      const data = err.response.data as Record<string, string[] | string>;
      const first = Object.values(data)[0];
      return Array.isArray(first) ? first[0] : String(first);
    }
    throw err;
  }
}
