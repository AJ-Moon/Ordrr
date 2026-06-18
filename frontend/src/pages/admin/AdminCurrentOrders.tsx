import { useEffect, useRef, useState } from "react";
import {
  RefreshCw,
  Phone,
  MapPin,
  Clock,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

function adminFetch(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem("admin_token");
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
}

interface OrderItem {
  name: string;
  quantity: number;
  price: number;
  category?: string;
}

interface Order {
  id: string;
  userId: string;
  customerName: string;
  customerPhone: string;
  guestName: string;
  guestPhone: string;
  items: OrderItem[];
  subtotal: number;
  total: number;
  status: string;
  orderType: string;
  paymentMethod: string;
  branchName: string;
  address: string;
  notes: string;
  createdAt: string;
  source: string;
}

const STATUS_STAGES = ["received", "preparing", "ready", "delivered"] as const;
type StageStatus = (typeof STATUS_STAGES)[number];

const STAGE_LABELS: Record<StageStatus, string> = {
  received: "Received",
  preparing: "Preparing",
  ready: "Ready",
  delivered: "Delivered",
};

const STATUS_CONFIG: Record<StageStatus, { label: string; color: string }> = {
  received: {
    label: "Received",
    color: "bg-yellow-100 text-yellow-800 border-yellow-200",
  },
  preparing: {
    label: "Preparing",
    color: "bg-orange-100 text-orange-800 border-orange-200",
  },
  ready: {
    label: "Ready",
    color: "bg-purple-100 text-purple-800 border-purple-200",
  },
  delivered: {
    label: "Delivered",
    color: "bg-green-100 text-green-800 border-green-200",
  },
};

function normalizeStageStatus(status: string): StageStatus {
  if (status === "delivered") return "delivered";
  if (status === "ready" || status === "out_for_delivery") return "ready";
  if (status === "preparing") return "preparing";
  return "received";
}

const ORDER_TYPE_COLOR: Record<string, string> = {
  delivery: "bg-blue-50 text-blue-700 border-blue-200",
  pickup: "bg-amber-50 text-amber-700 border-amber-200",
  "dine-in": "bg-emerald-50 text-emerald-700 border-emerald-200",
};

function timeAgo(isoDate: string) {
  const diff = Math.floor((Date.now() - new Date(isoDate).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export default function AdminCurrentOrders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [realtimeStatus, setRealtimeStatus] = useState<
    "connecting" | "live" | "off"
  >("connecting");
  // Keep a stable ref so the realtime callback can always call the latest fetchOrders
  const fetchOrdersRef = useRef<() => Promise<void>>(() => Promise.resolve());

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const res = await adminFetch("/api/admin/orders/current");
      if (res.ok) setOrders(await res.json());
    } finally {
      setLoading(false);
    }
  };

  fetchOrdersRef.current = fetchOrders;

  useEffect(() => {
    // SECURITY: Live order updates are fetched through the tenant-scoped admin API
    // (server enforces auth + restaurant_id). We deliberately do NOT subscribe to
    // Supabase Realtime from the browser: the anon key is public and, without RLS,
    // a postgres_changes subscription would stream other tenants' order PII over the
    // websocket regardless of the client-side filter. Polling keeps isolation server-side.
    fetchOrdersRef.current();
    setRealtimeStatus("live");

    const interval = window.setInterval(() => {
      fetchOrdersRef.current();
    }, 15000);

    const onVisible = () => {
      if (document.visibilityState === "visible") fetchOrdersRef.current();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  const updateStatus = async (orderId: string, status: string) => {
    setUpdatingId(orderId);
    try {
      const res = await adminFetch(`/api/admin/orders/${orderId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      if (res.ok) {
        const updated: Order = await res.json();
        if (status === "delivered" || status === "cancelled") {
          setOrders((prev) => prev.filter((o) => o.id !== orderId));
        } else {
          setOrders((prev) =>
            prev.map((o) => (o.id === orderId ? updated : o)),
          );
        }
      }
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Current Orders</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {loading
              ? "Loading…"
              : `${orders.length} active order${orders.length !== 1 ? "s" : ""} · ${
                  realtimeStatus === "live"
                    ? "live updates on"
                    : realtimeStatus === "connecting"
                      ? "connecting…"
                      : "realtime off — refresh manually"
                }`}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchOrders}
          disabled={loading}
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}
          />{" "}
          Refresh
        </Button>
      </div>

      {loading && (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border bg-card shadow-sm overflow-hidden"
            >
              <div className="flex items-center gap-4 px-5 py-4 border-b bg-muted/30">
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-5 w-16 rounded-full" />
                <Skeleton className="h-4 w-16 ml-auto" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 px-5 py-4">
                <div className="space-y-2">
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-5 w-32" />
                </div>
                <div className="space-y-2">
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-5 w-40" />
                </div>
                <div className="space-y-2">
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-5 w-24" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && orders.length === 0 && (
        <div className="rounded-xl border bg-card p-16 text-center text-muted-foreground">
          No active orders right now
        </div>
      )}

      <div className="space-y-4">
        {orders.map((order) => {
          const stageStatus = normalizeStageStatus(order.status);
          const cfg = STATUS_CONFIG[stageStatus];
          const isExpanded = expandedId === order.id;
          const isUpdating = updatingId === order.id;
          const customer = order.customerName || order.guestName || "Guest";
          const phone = order.customerPhone || order.guestPhone || "";
          const currentStageIndex = STATUS_STAGES.indexOf(stageStatus);

          return (
            <div
              key={order.id}
              className="rounded-xl border bg-card shadow-sm overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-center gap-4 px-5 py-4 border-b bg-muted/30">
                <div className="font-mono font-bold text-base">{order.id}</div>

                <span
                  className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${cfg?.color || "bg-gray-100 text-gray-700"}`}
                >
                  {cfg?.label || order.status.replace(/_/g, " ")}
                </span>

                <span
                  className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${ORDER_TYPE_COLOR[order.orderType] || "bg-gray-50 text-gray-700"}`}
                >
                  {order.orderType}
                </span>

                {order.source && order.source !== "online" && (
                  <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs bg-zinc-100 text-zinc-700 capitalize">
                    {order.source}
                  </span>
                )}

                <div className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" />
                  {timeAgo(order.createdAt)}
                </div>

                <button
                  onClick={() => setExpandedId(isExpanded ? null : order.id)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </button>
              </div>

              {/* Body */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 px-5 py-4">
                {/* Customer */}
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">
                    Customer
                  </p>
                  <p className="font-medium">{customer}</p>
                  {phone && (
                    <a
                      href={`tel:${phone}`}
                      className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mt-0.5"
                    >
                      <Phone className="h-3.5 w-3.5" /> {phone}
                    </a>
                  )}
                </div>

                {/* Branch / Address */}
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">
                    {order.orderType === "delivery"
                      ? "Delivery Address"
                      : "Branch"}
                  </p>
                  <p className="text-sm flex items-start gap-1">
                    <MapPin className="h-3.5 w-3.5 mt-0.5 shrink-0 text-muted-foreground" />
                    {order.orderType === "delivery"
                      ? order.address || "—"
                      : order.branchName || "—"}
                  </p>
                </div>

                {/* Payment & Total */}
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">
                    Payment
                  </p>
                  <p className="font-semibold text-lg">
                    ${order.total.toFixed(2)}
                  </p>
                  <p className="text-sm text-muted-foreground capitalize">
                    {order.paymentMethod}
                  </p>
                </div>
              </div>

              {/* Items summary (always visible, compact) */}
              <div className="px-5 pb-3">
                <p className="text-xs font-medium text-muted-foreground mb-1.5">
                  Items
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {order.items.map((item, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center rounded-md bg-secondary px-2 py-0.5 text-xs"
                    >
                      {item.quantity}× {item.name}
                    </span>
                  ))}
                </div>
                {order.notes && (
                  <p className="mt-2 text-xs text-muted-foreground italic">
                    Note: {order.notes}
                  </p>
                )}
              </div>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="border-t px-5 py-3 bg-muted/20">
                  <table className="w-full text-sm">
                    <tbody>
                      {order.items.map((item, i) => (
                        <tr key={i} className="border-b last:border-0">
                          <td className="py-1.5">{item.name}</td>
                          <td className="py-1.5 text-muted-foreground text-center">
                            {item.quantity}×
                          </td>
                          <td className="py-1.5 text-right">
                            ${(item.price * item.quantity).toFixed(2)}
                          </td>
                        </tr>
                      ))}
                      <tr className="font-semibold">
                        <td colSpan={2} className="pt-2">
                          Total
                        </td>
                        <td className="pt-2 text-right">
                          ${order.total.toFixed(2)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}

              {/* Actions */}
              <div className="border-t px-5 py-3">
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  Status Progress
                </p>
                <div className="flex flex-wrap gap-2">
                  {STATUS_STAGES.map((stage, index) => {
                    const isCurrent = index === currentStageIndex;
                    const isPast = index < currentStageIndex;
                    const isNext = index === currentStageIndex + 1;
                    const disabled = isUpdating || !isNext;

                    return (
                      <button
                        key={stage}
                        onClick={() => updateStatus(order.id, stage)}
                        disabled={disabled}
                        className={cn(
                          "rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors",
                          isCurrent &&
                            "border-primary bg-primary text-primary-foreground",
                          isPast &&
                            "border-green-200 bg-green-50 text-green-700",
                          isNext &&
                            "border-primary/40 bg-primary/10 text-primary hover:bg-primary/20",
                          disabled && !isCurrent && !isPast && "opacity-50",
                        )}
                      >
                        {isUpdating && isNext
                          ? "Updating…"
                          : STAGE_LABELS[stage]}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
