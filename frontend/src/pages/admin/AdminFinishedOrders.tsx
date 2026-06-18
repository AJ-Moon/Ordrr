import { useEffect, useRef, useState } from "react";
import { useDebounce } from "@/hooks/use-debounce";
import {
  Search,
  Download,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  X,
  Filter,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

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
}
interface Branch {
  id: number;
  name: string;
}
interface Order {
  id: string;
  customerName: string;
  customerPhone: string;
  guestName: string;
  guestPhone: string;
  items: OrderItem[];
  total: number;
  subtotal: number;
  discountAmount: number;
  deliveryCharge: number;
  status: string;
  orderType: string;
  paymentMethod: string;
  branchName: string;
  branchId: number | null;
  address: string;
  notes: string;
  pointsEarned: number;
  pointsRedeemed: number;
  createdAt: string;
  source: string;
}

const STATUS_COLOR: Record<string, string> = {
  delivered: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
};

export default function AdminFinishedOrders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [branchId, setBranchId] = useState("");
  const [status, setStatus] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");

  const buildUrl = (extra = "") => {
    const params = new URLSearchParams();
    if (debouncedSearch) params.set("search", debouncedSearch);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (branchId && branchId !== "all") params.set("branch_id", branchId);
    if (status && status !== "all") params.set("status", status);
    if (paymentMethod && paymentMethod !== "all")
      params.set("payment_method", paymentMethod);
    if (extra) params.set("export", extra);
    return `/api/admin/orders/finished?${params}`;
  };

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const res = await adminFetch(buildUrl());
      if (res.ok) setOrders(await res.json());
    } finally {
      setLoading(false);
    }
  };

  const fetchBranches = async () => {
    const res = await adminFetch("/api/admin/branches");
    if (res.ok) setBranches(await res.json());
  };

  useEffect(() => {
    fetchBranches();
  }, []);
  // debouncedSearch prevents a fetch on every keystroke; other filters fire immediately
  useEffect(() => {
    fetchOrders();
  }, [debouncedSearch, dateFrom, dateTo, branchId, status, paymentMethod]);

  const exportCsv = async () => {
    const res = await adminFetch(buildUrl("csv"));
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "orders.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const clearFilters = () => {
    setSearch("");
    setDateFrom("");
    setDateTo("");
    setBranchId("");
    setStatus("");
    setPaymentMethod("");
  };

  const hasFilters =
    search || dateFrom || dateTo || branchId || status || paymentMethod;

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">Finished Orders</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {loading
              ? "Loading…"
              : `${orders.length} order${orders.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <div className="flex gap-2">
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
          <Button variant="outline" size="sm" onClick={exportCsv}>
            <Download className="mr-2 h-4 w-4" /> Export CSV
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-4 rounded-xl border bg-card p-4 space-y-3">
        <div className="flex items-center gap-2 mb-1">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Filters</span>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="ml-auto flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive"
            >
              <X className="h-3 w-3" /> Clear all
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
          <div className="relative xl:col-span-2">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Order # or customer…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9 text-sm"
            />
          </div>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="h-9 text-sm"
            placeholder="From"
          />
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="h-9 text-sm"
            placeholder="To"
          />
          <Select
            value={branchId || "all"}
            onValueChange={(v) => setBranchId(v === "all" ? "" : v)}
          >
            <SelectTrigger className="h-9 text-sm">
              <SelectValue placeholder="All branches" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All branches</SelectItem>
              {branches.map((b) => (
                <SelectItem key={b.id} value={String(b.id)}>
                  {b.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={status || "all"}
            onValueChange={(v) => setStatus(v === "all" ? "" : v)}
          >
            <SelectTrigger className="h-9 text-sm">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="delivered">Delivered</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={paymentMethod || "all"}
            onValueChange={(v) => setPaymentMethod(v === "all" ? "" : v)}
          >
            <SelectTrigger className="h-9 text-sm">
              <SelectValue placeholder="All payments" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All payments</SelectItem>
              <SelectItem value="cash">Cash</SelectItem>
              <SelectItem value="card">Card</SelectItem>
              <SelectItem value="online">Online</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border bg-card overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/40 text-muted-foreground text-xs uppercase">
              <th className="px-4 py-3 text-left">Order</th>
              <th className="px-4 py-3 text-left">Customer</th>
              <th className="px-4 py-3 text-left">Branch</th>
              <th className="px-4 py-3 text-left">Date</th>
              <th className="px-4 py-3 text-left">Items</th>
              <th className="px-4 py-3 text-right">Total</th>
              <th className="px-4 py-3 text-left">Payment</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-center">Detail</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td
                  colSpan={9}
                  className="text-center py-16 text-muted-foreground"
                >
                  Loading…
                </td>
              </tr>
            ) : orders.length === 0 ? (
              <tr>
                <td
                  colSpan={9}
                  className="text-center py-16 text-muted-foreground"
                >
                  No orders found
                </td>
              </tr>
            ) : (
              orders.map((order) => {
                const isExpanded = expandedId === order.id;
                const customer =
                  order.customerName || order.guestName || "Guest";
                const phone = order.customerPhone || order.guestPhone || "";

                return (
                  <>
                    <tr
                      key={order.id}
                      className="border-b hover:bg-muted/20 cursor-pointer"
                      onClick={() =>
                        setExpandedId(isExpanded ? null : order.id)
                      }
                    >
                      <td className="px-4 py-3 font-mono font-semibold text-xs">
                        {order.id}
                      </td>
                      <td className="px-4 py-3">
                        <div>{customer}</div>
                        {phone && (
                          <div className="text-xs text-muted-foreground">
                            {phone}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {order.branchName || "—"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                        {new Date(order.createdAt).toLocaleDateString()}{" "}
                        <span className="text-xs">
                          {new Date(order.createdAt).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </td>
                      <td className="px-4 py-3 max-w-[200px]">
                        <div className="truncate text-xs text-muted-foreground">
                          {order.items
                            .map((i) => `${i.quantity}× ${i.name}`)
                            .join(", ")}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right font-semibold">
                        ${order.total.toFixed(2)}
                      </td>
                      <td className="px-4 py-3 capitalize text-muted-foreground">
                        {order.paymentMethod}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_COLOR[order.status] || "bg-gray-100 text-gray-700"}`}
                        >
                          {order.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center text-muted-foreground">
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4 inline" />
                        ) : (
                          <ChevronDown className="h-4 w-4 inline" />
                        )}
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr
                        key={`${order.id}-detail`}
                        className="bg-muted/10 border-b"
                      >
                        <td colSpan={9} className="px-6 py-4">
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            {/* Items */}
                            <div>
                              <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">
                                Order Items
                              </p>
                              <table className="w-full text-sm">
                                <tbody>
                                  {order.items.map((item, i) => (
                                    <tr
                                      key={i}
                                      className="border-b last:border-0"
                                    >
                                      <td className="py-1">{item.name}</td>
                                      <td className="py-1 text-center text-muted-foreground">
                                        {item.quantity}×
                                      </td>
                                      <td className="py-1 text-right">
                                        $
                                        {(item.price * item.quantity).toFixed(
                                          2,
                                        )}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                            {/* Breakdown */}
                            <div>
                              <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">
                                Totals
                              </p>
                              <div className="space-y-1 text-sm">
                                <div className="flex justify-between">
                                  <span>Subtotal</span>
                                  <span>${order.subtotal.toFixed(2)}</span>
                                </div>
                                {order.discountAmount > 0 && (
                                  <div className="flex justify-between text-green-600">
                                    <span>Discount</span>
                                    <span>
                                      -${order.discountAmount.toFixed(2)}
                                    </span>
                                  </div>
                                )}
                                {order.deliveryCharge > 0 && (
                                  <div className="flex justify-between">
                                    <span>Delivery</span>
                                    <span>
                                      ${order.deliveryCharge.toFixed(2)}
                                    </span>
                                  </div>
                                )}
                                <div className="flex justify-between font-bold border-t pt-1">
                                  <span>Total</span>
                                  <span>${order.total.toFixed(2)}</span>
                                </div>
                              </div>
                            </div>
                            {/* Meta */}
                            <div>
                              <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">
                                Details
                              </p>
                              <div className="space-y-1 text-sm">
                                <div>
                                  <span className="text-muted-foreground">
                                    Type:{" "}
                                  </span>
                                  {order.orderType}
                                </div>
                                <div>
                                  <span className="text-muted-foreground">
                                    Source:{" "}
                                  </span>
                                  {order.source}
                                </div>
                                {order.address && (
                                  <div>
                                    <span className="text-muted-foreground">
                                      Address:{" "}
                                    </span>
                                    {order.address}
                                  </div>
                                )}
                                {order.notes && (
                                  <div>
                                    <span className="text-muted-foreground">
                                      Notes:{" "}
                                    </span>
                                    {order.notes}
                                  </div>
                                )}
                                {order.pointsEarned > 0 && (
                                  <div>
                                    <span className="text-muted-foreground">
                                      Points earned:{" "}
                                    </span>
                                    {order.pointsEarned}
                                  </div>
                                )}
                                {order.pointsRedeemed > 0 && (
                                  <div>
                                    <span className="text-muted-foreground">
                                      Points redeemed:{" "}
                                    </span>
                                    {order.pointsRedeemed}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
