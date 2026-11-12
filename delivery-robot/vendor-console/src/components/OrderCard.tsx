import type { Order, OrderStatus } from "../types";

interface OrderCardProps {
  order: Order;
  isNew?: boolean;
  isLight?: boolean;
  onUpdateStatus: (id: string, status: OrderStatus) => void;
}

function timeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}

const STATUS_NEXT: Partial<Record<OrderStatus, { label: string; next: OrderStatus }>> = {
  ACCEPTED:  { label: "Start Preparing", next: "PREPARING" },
  PREPARING: { label: "Mark Ready",      next: "READY" },
};

export default function OrderCard({ order, isNew, isLight = false, onUpdateStatus }: OrderCardProps) {
  const nextAction = STATUS_NEXT[order.status];

  return (
    <div
      className={[
        "rounded-lg border p-3 flex flex-col gap-2.5 transition-all duration-200",
        isLight ? "bg-white" : "bg-zinc-900",
        isNew
          ? "border-orange-500 shadow-[0_0_14px_rgba(249,115,22,0.25)] animate-pulse-once"
          : isLight
            ? "border-zinc-300 hover:border-zinc-400"
            : "border-zinc-700/60 hover:border-zinc-600",
      ].join(" ")}
    >
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className={`font-mono text-sm font-semibold ${isLight ? "text-zinc-900" : "text-zinc-100"}`}>
          {order.orderNumber}
        </span>
        <span className={`font-mono text-[11px] ${isLight ? "text-zinc-600" : "text-zinc-500"}`}>
          {timeAgo(order.createdAt)}
        </span>
      </div>

      {/* Student + location */}
      <div className="flex flex-col gap-0.5">
        <span className={`text-[13px] font-medium ${isLight ? "text-zinc-800" : "text-zinc-200"}`}>
          {order.studentName}
        </span>
        <span className={`flex items-center gap-1 text-[11px] ${isLight ? "text-zinc-600" : "text-zinc-500"}`}>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="shrink-0">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
          {order.deliveryLocation}
        </span>
      </div>

      {/* Items */}
      <ul className={`rounded px-2.5 py-2 flex flex-col gap-1.5 border ${isLight ? "bg-zinc-100 border-zinc-200" : "bg-zinc-800/70 border-zinc-700/50"}`}>
        {order.items.map((item) => (
          <li key={item.id} className="flex items-baseline gap-1.5 flex-wrap">
            <span className={`font-mono text-[11px] font-semibold w-5 shrink-0 ${isLight ? "text-zinc-600" : "text-zinc-500"}`}>
              {item.quantity}×
            </span>
            <span className={`text-[12px] ${isLight ? "text-zinc-800" : "text-zinc-200"}`}>{item.name}</span>
            {item.customisation && (
              <span className="font-mono text-[10px] text-amber-400 bg-amber-400/10 border border-amber-400/20 px-1.5 py-px rounded">
                {item.customisation}
              </span>
            )}
          </li>
        ))}
      </ul>

      {/* Accept / Reject */}
      {order.status === "PLACED" && (
        <div className="flex gap-2">
          <button
            onClick={() => onUpdateStatus(order.id, "REJECTED")}
            className={`flex-1 py-1.5 rounded text-[12px] font-semibold text-red-400 border border-red-500/25 hover:bg-red-500/10 transition-colors ${isLight ? "bg-zinc-100" : "bg-zinc-800"}`}
          >
            Reject
          </button>
          <button
            onClick={() => onUpdateStatus(order.id, "ACCEPTED")}
            className="flex-1 py-1.5 rounded text-[12px] font-semibold text-black bg-green-400 hover:bg-green-300 transition-colors"
          >
            Accept
          </button>
        </div>
      )}

      {/* Status progression */}
      {nextAction && (
        <button
          onClick={() => onUpdateStatus(order.id, nextAction.next)}
          className={`w-full py-1.5 rounded text-[12px] font-semibold border hover:border-blue-500 hover:text-blue-400 transition-colors ${isLight ? "text-zinc-700 bg-zinc-100 border-zinc-300" : "text-zinc-200 bg-zinc-800 border-zinc-700"}`}
        >
          {nextAction.label} →
        </button>
      )}

      {/* Ready state */}
      {order.status === "READY" && (
        <div className="flex items-center gap-1.5 font-mono text-[11px] text-green-400">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          Awaiting robot dispatch
        </div>
      )}

      {/* Dispatched state */}
      {order.status === "DISPATCHED" && (
        <div className="flex items-center gap-1.5 font-mono text-[11px] text-blue-400">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          Robot dispatched — on the way
        </div>
      )}

      {/* Rejected state */}
      {order.status === "REJECTED" && (
        <p className={`font-mono text-[10px] line-through ${isLight ? "text-zinc-500" : "text-zinc-600"}`}>
          Order rejected
        </p>
      )}
    </div>
  );
}
