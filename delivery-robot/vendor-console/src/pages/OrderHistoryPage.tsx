import { useMemo, useState } from "react";
import type { Order, OrderStatus } from "../types";

interface OrderHistoryPageProps {
  orders: Order[];
  isLight?: boolean;
}

const HISTORY_STATUSES: OrderStatus[] = ["DELIVERED", "REJECTED", "CANCELLED", "FALLBACK"];

export default function OrderHistoryPage({ orders, isLight = false }: OrderHistoryPageProps) {
  const [status, setStatus] = useState<"ALL" | OrderStatus>("ALL");
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    return orders
      .filter((o) => HISTORY_STATUSES.includes(o.status))
      .filter((o) => (status === "ALL" ? true : o.status === status))
      .filter((o) => {
        const term = query.toLowerCase();
        return (
          o.orderNumber.toLowerCase().includes(term) ||
          o.studentName.toLowerCase().includes(term)
        );
      })
      .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime());
  }, [orders, query, status]);

  return (
    <div className="p-5 h-full overflow-y-auto">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-mono text-lg font-semibold">Order History</h2>
        <span className="text-xs text-zinc-400">{rows.length} orders</span>
      </div>

      <div className="flex gap-3 mb-4">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search order # or student..."
          className={`flex-1 px-3 py-2 rounded border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-800 border-zinc-700"}`}
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as "ALL" | OrderStatus)}
          className={`px-3 py-2 rounded border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-800 border-zinc-700"}`}
        >
          <option value="ALL">All statuses</option>
          <option value="DELIVERED">Delivered</option>
          <option value="REJECTED">Rejected</option>
          <option value="CANCELLED">Cancelled</option>
          <option value="FALLBACK">Fallback</option>
        </select>
      </div>

      <div className={`overflow-hidden rounded border ${isLight ? "border-zinc-300 bg-white" : "border-zinc-800"}`}>
        <table className="w-full text-sm">
          <thead className={isLight ? "bg-zinc-100 text-zinc-600" : "bg-zinc-900 text-zinc-400"}>
            <tr>
              <th className="text-left px-3 py-2">Order</th>
              <th className="text-left px-3 py-2">Student</th>
              <th className="text-left px-3 py-2">Items</th>
              <th className="text-left px-3 py-2">Status</th>
              <th className="text-left px-3 py-2">Updated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((order) => (
              <tr key={order.id} className={`border-t ${isLight ? "border-zinc-200" : "border-zinc-800"}`}>
                <td className="px-3 py-2 font-mono">{order.orderNumber}</td>
                <td className="px-3 py-2">{order.studentName}</td>
                <td className="px-3 py-2">{order.items.length}</td>
                <td className="px-3 py-2">{order.status}</td>
                <td className="px-3 py-2">{order.updatedAt.toLocaleString()}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className="px-3 py-6 text-zinc-500 text-center" colSpan={5}>
                  No order history matches your filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
