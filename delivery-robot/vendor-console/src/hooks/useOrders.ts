import { useCallback, useEffect, useRef, useState } from "react";
import { fetchOrder, fetchOrders, patchOrderStatus } from "../api/orders";
import type { Order, OrderStatus } from "../types";

const WS_URL = `${import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000"}/ws/orders/`;

interface WsPayload {
  id: number;
  status: string;
  vendor_id: number;
  delivery_location: string;
  updated_at: string;
}

interface UseOrdersOptions {
  autoAcceptOrders?: boolean;
  /** When set, list/detail APIs and WS payloads are scoped to this vendor. */
  vendorId?: number | null;
}

export function useOrders(options: UseOrdersOptions = {}) {
  const { autoAcceptOrders = false, vendorId = null } = options;

  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newOrderIds, setNewOrderIds] = useState<Set<string>>(new Set());

  // Refs so WS callbacks always see the latest values without re-running effects
  const autoAcceptRef = useRef(autoAcceptOrders);
  autoAcceptRef.current = autoAcceptOrders;

  const knownIdsRef = useRef<Set<string>>(new Set());

  // ── Initial load ──────────────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;
    setError(null);

    if (vendorId == null) {
      setOrders([]);
      knownIdsRef.current = new Set();
      setIsLoading(true);
      return;
    }

    setIsLoading(true);

    fetchOrders()
      .then((initial) => {
        if (cancelled) return;
        setOrders(initial);
        knownIdsRef.current = new Set(initial.map((o) => o.id));
        setIsLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("Failed to load orders:", err);
        setError("Could not load orders. Check that the backend is running.");
        setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [vendorId]);

  // ── WebSocket with exponential-backoff reconnect ──────────────────────────

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let retryDelay = 1000;
    let destroyed = false;

    function connect() {
      ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        retryDelay = 1000; // reset backoff on a clean connect
      };

      ws.onmessage = async (event: MessageEvent<string>) => {
        let payload: WsPayload;
        try {
          payload = JSON.parse(event.data) as WsPayload;
        } catch {
          return;
        }

        if (vendorId != null && payload.vendor_id !== vendorId) {
          return;
        }

        const id = String(payload.id);

        if (knownIdsRef.current.has(id)) {
          // Patch status on an existing order
          setOrders((prev) =>
            prev.map((o) =>
              o.id === id
                ? { ...o, status: payload.status as OrderStatus, updatedAt: new Date(payload.updated_at) }
                : o,
            ),
          );
        } else {
          // Brand-new order: fetch full details then add to state
          try {
            const newOrder = await fetchOrder(id);
            if (autoAcceptRef.current) {
              newOrder.status = "ACCEPTED";
            }
            knownIdsRef.current.add(id);
            setOrders((prev) => [newOrder, ...prev]);
            setNewOrderIds((prev) => new Set(prev).add(id));
            setTimeout(() => {
              setNewOrderIds((prev) => {
                const next = new Set(prev);
                next.delete(id);
                return next;
              });
            }, 4000);
          } catch (err) {
            console.error("Failed to fetch new order details:", id, err);
          }
        }
      };

      ws.onerror = () => {
        ws?.close();
      };

      ws.onclose = () => {
        if (destroyed) return;
        retryTimer = setTimeout(() => {
          retryDelay = Math.min(retryDelay * 2, 30_000);
          connect();
        }, retryDelay);
      };
    }

    connect();

    return () => {
      destroyed = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    };
  }, [vendorId]);

  // ── Actions ───────────────────────────────────────────────────────────────

  const updateOrderStatus = useCallback(
    async (orderId: string, status: OrderStatus, vendorNote?: string) => {
      // Optimistic update so the UI feels instant
      setOrders((prev) =>
        prev.map((o) =>
          o.id === orderId ? { ...o, status, updatedAt: new Date() } : o,
        ),
      );

      try {
        const updated = await patchOrderStatus(orderId, status, vendorNote);
        // Apply confirmed server state
        setOrders((prev) => prev.map((o) => (o.id === orderId ? updated : o)));
      } catch (err) {
        console.error("Failed to update order status:", err);
        // Revert optimistic update by re-fetching
        try {
          const reverted = await fetchOrder(orderId);
          setOrders((prev) => prev.map((o) => (o.id === orderId ? reverted : o)));
        } catch {
          // Ignore — stale state is acceptable until next WS update
        }
      }
    },
    [],
  );

  // ── Derived slices ────────────────────────────────────────────────────────

  return {
    allOrders: orders,
    newOrders: orders.filter((o) => o.status === "PLACED"),
    acceptedOrders: orders.filter((o) => o.status === "ACCEPTED"),
    preparingOrders: orders.filter((o) => o.status === "PREPARING"),
    readyOrders: orders.filter((o) => o.status === "READY"),
    dispatchedOrders: orders.filter((o) => o.status === "DISPATCHED"),
    isLoading,
    error,
    newOrderIds,
    updateOrderStatus,
  };
}
