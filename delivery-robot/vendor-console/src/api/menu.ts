import type { MenuItem } from "../types";
import apiClient from "./client";

// ── Enrichment layer ──────────────────────────────────────────────────────────
// The backend MenuItem model has no `category` or `imageUrl` fields.
// We store those client-side in localStorage keyed by item ID, and merge them
// on read. When the backend eventually gains these fields, this layer can be
// removed and the mappers updated.

/** Legacy global key — migrated per-vendor on first read. */
const LEGACY_ENRICHMENT_KEY = "vendor_menu_enrichment_v1";

function enrichmentStorageKey(vendorId: number): string {
  return `vendor_menu_enrichment_v1_v${vendorId}`;
}

interface Enrichment {
  category: string;
  imageUrl: string;
}

function loadEnrichment(vendorId: number): Record<string, Enrichment> {
  try {
    const key = enrichmentStorageKey(vendorId);
    let raw = localStorage.getItem(key);
    if (!raw) {
      const legacy = localStorage.getItem(LEGACY_ENRICHMENT_KEY);
      if (legacy) {
        raw = legacy;
        try {
          localStorage.setItem(key, legacy);
          localStorage.removeItem(LEGACY_ENRICHMENT_KEY);
        } catch {
          /* ignore quota */
        }
      }
    }
    return JSON.parse(raw ?? "{}") as Record<string, Enrichment>;
  } catch {
    return {};
  }
}

function saveEnrichment(vendorId: number, map: Record<string, Enrichment>): void {
  try {
    localStorage.setItem(enrichmentStorageKey(vendorId), JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

function setItemEnrichment(vendorId: number, id: string, data: Enrichment): void {
  const map = loadEnrichment(vendorId);
  map[id] = data;
  saveEnrichment(vendorId, map);
}

function removeItemEnrichment(vendorId: number, id: string): void {
  const map = loadEnrichment(vendorId);
  delete map[id];
  saveEnrichment(vendorId, map);
}

// ── Raw shapes from the backend ───────────────────────────────────────────────

interface RawMenuItem {
  id: number;
  vendor: number;
  name: string;
  description: string;
  price: string;
  is_available: boolean;
  prep_time_minutes: number;
}

// ── Mapper ────────────────────────────────────────────────────────────────────

export function mapMenuItemRaw(raw: RawMenuItem, enrichment: Record<string, Enrichment>): MenuItem {
  const id = String(raw.id);
  const e = enrichment[id] ?? { category: "", imageUrl: "" };
  return {
    id,
    name: raw.name,
    description: raw.description,
    price: parseFloat(raw.price),
    isAvailable: raw.is_available,
    prepTimeMins: raw.prep_time_minutes,
    category: e.category,
    imageUrl: e.imageUrl,
  };
}

// ── API calls ─────────────────────────────────────────────────────────────────

export async function fetchMenuItems(vendorId: number): Promise<MenuItem[]> {
  const { data } = await apiClient.get<RawMenuItem[]>("/api/menu/items/");
  const enrichment = loadEnrichment(vendorId);
  return data.map((raw) => mapMenuItemRaw(raw, enrichment));
}

export interface MenuItemFormData {
  vendorId: number;
  name: string;
  description: string;
  price: number;
  isAvailable: boolean;
  prepTimeMins: number;
  category: string;
  imageUrl: string;
}

export async function createMenuItem(form: MenuItemFormData): Promise<MenuItem> {
  const { data } = await apiClient.post<RawMenuItem>("/api/menu/items/", {
    vendor: form.vendorId,
    name: form.name,
    description: form.description,
    price: form.price,
    is_available: form.isAvailable,
    prep_time_minutes: form.prepTimeMins,
  });
  const id = String(data.id);
  setItemEnrichment(form.vendorId, id, { category: form.category, imageUrl: form.imageUrl });
  return mapMenuItemRaw(data, loadEnrichment(form.vendorId));
}

export async function updateMenuItem(
  vendorId: number,
  id: string,
  form: Partial<MenuItemFormData>,
): Promise<MenuItem> {
  const body: Record<string, unknown> = {};
  if (form.name !== undefined) body.name = form.name;
  if (form.description !== undefined) body.description = form.description;
  if (form.price !== undefined) body.price = form.price;
  if (form.isAvailable !== undefined) body.is_available = form.isAvailable;
  if (form.prepTimeMins !== undefined) body.prep_time_minutes = form.prepTimeMins;

  const { data } = await apiClient.patch<RawMenuItem>(`/api/menu/items/${id}/`, body);

  // Always update enrichment fields if provided
  if (form.category !== undefined || form.imageUrl !== undefined) {
    const existing = loadEnrichment(vendorId)[id] ?? { category: "", imageUrl: "" };
    setItemEnrichment(vendorId, id, {
      category: form.category ?? existing.category,
      imageUrl: form.imageUrl ?? existing.imageUrl,
    });
  }

  return mapMenuItemRaw(data, loadEnrichment(vendorId));
}

export async function deleteMenuItem(vendorId: number, id: string): Promise<void> {
  await apiClient.delete(`/api/menu/items/${id}/`);
  removeItemEnrichment(vendorId, id);
}
