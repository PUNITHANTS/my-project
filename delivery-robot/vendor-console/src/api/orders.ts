import type { Order, OrderStatus } from "../types";
import apiClient from "./client";

// ── Raw shapes returned by the backend ───────────────────────────────────────

interface RawOrderItem {
  id: number;
  menu_item: number;
  menu_item_name: string;
  quantity: number;
  customization: string;
  price_at_order: string;
}

interface RawOrder {
  id: number;
  student: number | null;
  student_name: string;
  phone: string;
  vendor: number;
  delivery_location: string;
  status: string;
  vendor_note: string;
  items: RawOrderItem[];
  created_at: string;
  updated_at: string;
}

// ── Mappers ───────────────────────────────────────────────────────────────────

function mapItem(raw: RawOrderItem): Order["items"][0] {
  return {
    id: String(raw.id),
    name: raw.menu_item_name,
    quantity: raw.quantity,
    customisation: raw.customization || undefined,
  };
}

export function mapOrder(raw: RawOrder): Order {
  return {
    id: String(raw.id),
    orderNumber: `#${raw.id}`,
    studentName: raw.student_name,
    deliveryLocation: raw.delivery_location,
    items: raw.items.map(mapItem),
    status: raw.status as OrderStatus,
    vendorNote: raw.vendor_note || undefined,
    createdAt: new Date(raw.created_at),
    updatedAt: new Date(raw.updated_at),
  };
}

// ── API calls ─────────────────────────────────────────────────────────────────

export async function fetchOrders(): Promise<Order[]> {
  const { data } = await apiClient.get<RawOrder[]>("/api/orders/");
  return data.map(mapOrder);
}

export async function fetchOrder(id: string): Promise<Order> {
  const { data } = await apiClient.get<RawOrder>(`/api/orders/${id}/`);
  return mapOrder(data);
}

export async function patchOrderStatus(
  id: string,
  status: OrderStatus,
  vendorNote?: string,
): Promise<Order> {
  const { data } = await apiClient.post<RawOrder>(`/api/orders/${id}/status/`, {
    status,
    vendor_note: vendorNote ?? "",
  });
  return mapOrder(data);
}
