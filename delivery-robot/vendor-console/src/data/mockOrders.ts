import type { Order } from "../types";

const LOCATIONS = [
  "Student Center – Table 4",
  "Library Entrance",
  "College Hall Lobby",
  "Science Hall – Bench 2",
  "University Hall Steps",
];

const MENU_POOL: { name: string; customisations: string[] }[] = [
  { name: "Chicken Caesar Wrap", customisations: ["no croutons", "extra dressing", ""] },
  { name: "Veggie Burger", customisations: ["no onions", "add avocado", ""] },
  { name: "Pepperoni Slice", customisations: ["extra cheese", "well done", ""] },
  { name: "Turkey Club", customisations: ["no mayo", "toasted", ""] },
  { name: "Mango Smoothie", customisations: ["no sugar", "extra ice", ""] },
  { name: "Grilled Cheese", customisations: ["add tomato", "sourdough", ""] },
  { name: "Falafel Bowl", customisations: ["extra tahini", "no pickles", ""] },
  { name: "Iced Coffee", customisations: ["oat milk", "extra shot", ""] },
];

const NAMES = [
  "Alex Rivera", "Jordan Kim", "Sam Patel", "Taylor Brooks",
  "Morgan Lee", "Casey Nguyen", "Jamie Torres", "Drew Okafor",
];

let orderCounter = 1042;

export function generateMockOrder(): Order {
  const numItems = Math.floor(Math.random() * 3) + 1;
  const items = Array.from({ length: numItems }, (_, i) => {
    const pool = MENU_POOL[Math.floor(Math.random() * MENU_POOL.length)];
    const customisation =
      pool.customisations[Math.floor(Math.random() * pool.customisations.length)];
    return {
      id: `item-${Date.now()}-${i}`,
      name: pool.name,
      quantity: Math.random() > 0.6 ? 2 : 1,
      customisation: customisation || undefined,
    };
  });

  orderCounter++;
  return {
    id: `order-${Date.now()}-${Math.random()}`,
    orderNumber: `#${orderCounter}`,
    studentName: NAMES[Math.floor(Math.random() * NAMES.length)],
    deliveryLocation: LOCATIONS[Math.floor(Math.random() * LOCATIONS.length)],
    items,
    status: "PLACED",
    createdAt: new Date(),
    updatedAt: new Date(),
  };
}

export const INITIAL_ORDERS: Order[] = [
  {
    id: "order-seed-1",
    orderNumber: "#1039",
    studentName: "Alex Rivera",
    deliveryLocation: "Student Center – Table 4",
    items: [
      { id: "i1", name: "Chicken Caesar Wrap", quantity: 1, customisation: "no croutons" },
      { id: "i2", name: "Iced Coffee", quantity: 1, customisation: "oat milk" },
    ],
    status: "PLACED",
    createdAt: new Date(Date.now() - 90000),
    updatedAt: new Date(Date.now() - 90000),
  },
  {
    id: "order-seed-2",
    orderNumber: "#1040",
    studentName: "Jordan Kim",
    deliveryLocation: "Library Entrance",
    items: [
      { id: "i3", name: "Veggie Burger", quantity: 1 },
      { id: "i4", name: "Mango Smoothie", quantity: 1 },
    ],
    status: "ACCEPTED",
    createdAt: new Date(Date.now() - 240000),
    updatedAt: new Date(Date.now() - 180000),
  },
  {
    id: "order-seed-3",
    orderNumber: "#1041",
    studentName: "Sam Patel",
    deliveryLocation: "College Hall Lobby",
    items: [
      { id: "i5", name: "Pepperoni Slice", quantity: 2, customisation: "extra cheese" },
    ],
    status: "PREPARING",
    createdAt: new Date(Date.now() - 420000),
    updatedAt: new Date(Date.now() - 300000),
  },
];
