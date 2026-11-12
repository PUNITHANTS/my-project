export type OrderStatus =
  | "PLACED"
  | "ACCEPTED"
  | "PREPARING"
  | "READY"
  | "DISPATCHED"
  | "DELIVERED"
  | "REJECTED"
  | "FALLBACK"
  | "CANCELLED";

export interface OrderItem {
  id: string;
  name: string;
  quantity: number;
  customisation?: string;
}

export interface Order {
  id: string;
  orderNumber: string;
  studentName: string;
  deliveryLocation: string;
  items: OrderItem[];
  status: OrderStatus;
  vendorNote?: string;
  createdAt: Date;
  updatedAt: Date;
}

export type AppTheme = "dark" | "light";
export type AppLanguage = "en" | "es";

export interface VendorSettings {
  businessName: string;
  contactEmail: string;
  contactPhone: string;
  pickupPrepTimeMins: number;
  isStoreOpen: boolean;
  hoursOfOperation: string;
  autoAcceptOrders: boolean;
  theme: AppTheme;
  language: AppLanguage;
  passwordHint: string;
  twoFactorEnabled: boolean;
}

export interface MenuItem {
  id: string;
  name: string;
  category: string;
  price: number;
  description: string;
  imageUrl: string;
  prepTimeMins: number;
  isAvailable: boolean;
}
