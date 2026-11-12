import apiClient from "./client";

// ── Raw shapes ────────────────────────────────────────────────────────────────

export interface RawVendor {
  id: number;
  name: string;
  location_label: string;
  is_active: boolean;
  intake_paused: boolean;
  manager: number | null;
}

export interface RawUser {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  role: string;
}

export interface VendorContext {
  user: RawUser;
  vendor: RawVendor;
}

// ── API calls ─────────────────────────────────────────────────────────────────

/**
 * Fetches the authenticated user and their vendor context concurrently.
 * Uses the first row returned by GET /api/vendors/ (sorted by name). Vendor
 * accounts should receive exactly one vendor; staff/superusers may receive many —
 * the console does not yet offer a tenant picker, so the first name-sort entry wins.
 */
export async function fetchVendorContext(): Promise<VendorContext> {
  const [userRes, vendorsRes] = await Promise.all([
    apiClient.get<RawUser>("/api/accounts/me/"),
    apiClient.get<RawVendor[]>("/api/vendors/"),
  ]);

  const vendor = vendorsRes.data[0];
  if (!vendor) throw new Error("No vendor account found for this user.");

  return { user: userRes.data, vendor };
}

export async function patchVendor(
  id: number,
  data: Partial<Pick<RawVendor, "name" | "intake_paused" | "is_active">>,
): Promise<RawVendor> {
  const { data: updated } = await apiClient.patch<RawVendor>(`/api/vendors/${id}/`, data);
  return updated;
}
