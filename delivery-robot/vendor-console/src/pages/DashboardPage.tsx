import type { Order, OrderStatus } from "../types";
import StatusColumn from "../components/StatusColumn";

interface DashboardPageProps {
  newOrders: Order[];
  acceptedOrders: Order[];
  preparingOrders: Order[];
  readyOrders: Order[];
  dispatchedOrders: Order[];
  isPaused: boolean;
  isLight?: boolean;
  newOrderIds: Set<string>;
  isLoading?: boolean;
  error?: string | null;
  onTogglePause: () => void;
  onUpdateStatus: (id: string, status: OrderStatus) => void;
}

export default function DashboardPage({
  newOrders,
  acceptedOrders,
  preparingOrders,
  readyOrders,
  dispatchedOrders,
  isPaused,
  isLight = false,
  newOrderIds,
  isLoading = false,
  error = null,
  onTogglePause,
  onUpdateStatus,
}: DashboardPageProps) {
  const totalActive = newOrders.length + acceptedOrders.length + preparingOrders.length;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className={`px-5 py-3 border-b flex items-center justify-between shrink-0 ${isLight ? "border-zinc-300 bg-white" : "border-zinc-800 bg-zinc-900/70"}`}>
        <div className="flex items-center gap-3">
          <div className={`flex items-baseline gap-1 px-2.5 py-1.5 border rounded ${isLight ? "bg-zinc-100 border-zinc-300" : "bg-zinc-800 border-zinc-700"}`}>
            <span className={`font-mono text-base font-semibold ${isLight ? "text-zinc-900" : "text-zinc-100"}`}>{totalActive}</span>
            <span className={`text-[11px] ${isLight ? "text-zinc-600" : "text-zinc-500"}`}>active</span>
          </div>
          <div className={`flex items-baseline gap-1 px-2.5 py-1.5 border rounded ${isLight ? "bg-zinc-100 border-zinc-300" : "bg-zinc-800 border-zinc-700"}`}>
            <span className={`font-mono text-base font-semibold ${isLight ? "text-zinc-900" : "text-zinc-100"}`}>{readyOrders.length}</span>
            <span className={`text-[11px] ${isLight ? "text-zinc-600" : "text-zinc-500"}`}>ready</span>
          </div>
        </div>

        <button
          onClick={onTogglePause}
          className={[
            "flex items-center gap-1.5 px-3.5 py-1.5 rounded text-[12px] font-semibold transition-colors",
            isPaused
              ? "bg-green-400 text-black hover:bg-green-300"
              : isLight
                ? "bg-white text-amber-600 border border-zinc-300 hover:bg-zinc-100"
                : "bg-zinc-800 text-amber-400 border border-zinc-700 hover:bg-zinc-700",
          ].join(" ")}
        >
          {isPaused ? "Resume Intake" : "Pause Intake"}
        </button>
      </div>

      {isPaused && (
        <div className="flex items-center justify-center gap-2 py-2 bg-amber-400/10 border-b border-amber-400/25 text-amber-400 font-mono text-[12px] font-medium tracking-wide shrink-0">
          Order intake is paused — no new orders are being accepted
        </div>
      )}

      {error && (
        <div className="flex items-center justify-center gap-2 py-2 bg-red-500/10 border-b border-red-500/25 text-red-400 font-mono text-[12px] shrink-0">
          {error}
        </div>
      )}

      <main className={`relative grid grid-cols-5 flex-1 gap-px overflow-hidden transition-opacity duration-300 ${isLight ? "bg-zinc-200" : "bg-zinc-800"} ${isPaused ? "opacity-70" : "opacity-100"}`}>
        {isLoading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/60 backdrop-blur-sm">
            <div className="flex items-center gap-3 font-mono text-sm text-zinc-300">
              <span className="w-4 h-4 rounded-full border-2 border-orange-500 border-t-transparent animate-spin" />
              Loading orders…
            </div>
          </div>
        )}
        <StatusColumn
          title="New Orders"
          accentClass="border-orange-500"
          countBgClass="bg-orange-500"
          orders={newOrders}
          newOrderIds={newOrderIds}
          isLight={isLight}
          onUpdateStatus={onUpdateStatus}
          emptyMessage="No new orders"
        />
        <StatusColumn
          title="Accepted"
          accentClass="border-blue-500"
          countBgClass="bg-blue-500"
          orders={acceptedOrders}
          newOrderIds={newOrderIds}
          isLight={isLight}
          onUpdateStatus={onUpdateStatus}
          emptyMessage="No accepted orders"
        />
        <StatusColumn
          title="Preparing"
          accentClass="border-purple-500"
          countBgClass="bg-purple-500"
          orders={preparingOrders}
          newOrderIds={newOrderIds}
          isLight={isLight}
          onUpdateStatus={onUpdateStatus}
          emptyMessage="No orders in prep"
        />
        <StatusColumn
          title="Ready"
          accentClass="border-green-500"
          countBgClass="bg-green-500"
          orders={readyOrders}
          newOrderIds={newOrderIds}
          isLight={isLight}
          onUpdateStatus={onUpdateStatus}
          emptyMessage="No orders ready"
        />
        <StatusColumn
          title="Dispatched"
          accentClass="border-sky-500"
          countBgClass="bg-sky-500"
          orders={dispatchedOrders}
          newOrderIds={newOrderIds}
          isLight={isLight}
          onUpdateStatus={onUpdateStatus}
          emptyMessage="No orders en route"
        />
      </main>
    </div>
  );
}
