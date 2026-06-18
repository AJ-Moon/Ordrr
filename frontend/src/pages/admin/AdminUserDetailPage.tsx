import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Star,
  ShoppingBag,
  TrendingUp,
  Calendar,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

function adminFetch(url: string) {
  const token = localStorage.getItem("admin_token");
  return fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
}

interface UserInfo {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  phone: string;
  createdAt: string;
  points: number;
}
interface Summary {
  totalOrders: number;
  totalSpent: number;
  avgOrderValue: number;
  firstOrder: string | null;
  lastOrder: string | null;
  favoriteCategory: string;
}
interface CategoryItem {
  category: string;
  quantity: number;
  totalSpent: number;
  topItem: string;
}
interface ItemRow {
  name: string;
  category: string;
  quantity: number;
  totalSpent: number;
  lastOrdered: string;
}
interface Order {
  id: string;
  items: { name: string; quantity: number; price: number }[];
  total: number;
  status: string;
  orderType: string;
  createdAt: string;
  source: string;
  branchName: string;
  paymentMethod: string;
}

const STATUS_COLOR: Record<string, string> = {
  placed: "bg-yellow-100 text-yellow-800",
  confirmed: "bg-blue-100 text-blue-800",
  preparing: "bg-orange-100 text-orange-800",
  ready: "bg-purple-100 text-purple-800",
  out_for_delivery: "bg-indigo-100 text-indigo-800",
  delivered: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
};

export default function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();

  const [data, setData] = useState<{
    user: UserInfo;
    summary: Summary;
    categoryBreakdown: CategoryItem[];
    itemBreakdown: ItemRow[];
    orders: Order[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "items" | "orders">(
    "overview",
  );

  useEffect(() => {
    if (!userId) return;
    setLoading(true);
    adminFetch(`/api/admin/users/${userId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) setData(d);
      })
      .finally(() => setLoading(false));
  }, [userId]);

  if (loading)
    return (
      <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
        <Skeleton className="h-5 w-36" />
        <div className="flex items-center gap-4">
          <Skeleton className="h-16 w-16 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-7 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-10 w-64" />
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      </div>
    );
  if (!data)
    return <div className="p-8 text-destructive">Customer not found.</div>;

  const { user, summary, categoryBreakdown, itemBreakdown, orders } = data;
  const fullName = `${user.firstName} ${user.lastName}`.trim() || user.email;

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto">
      {/* Back */}
      <button
        onClick={() => navigate("/admin/users")}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-5"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Customers
      </button>

      {/* Header */}
      <div className="flex items-start gap-4 mb-6">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground text-xl font-bold shrink-0">
          {(user.firstName?.[0] || user.email[0] || "?").toUpperCase()}
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{fullName}</h1>
          <p className="text-muted-foreground text-sm">{user.email}</p>
          {user.phone && (
            <p className="text-muted-foreground text-sm">{user.phone}</p>
          )}
          <p className="text-xs text-muted-foreground mt-1">
            Joined{" "}
            {user.createdAt
              ? new Date(user.createdAt).toLocaleDateString()
              : "—"}
          </p>
        </div>
        <div className="text-right">
          <div className="inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-800 px-3 py-1 text-sm font-semibold">
            <Star className="h-3.5 w-3.5" /> {user.points} points
          </div>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          {
            label: "Total Orders",
            value: summary.totalOrders,
            icon: ShoppingBag,
          },
          {
            label: "Total Spent",
            value: `$${summary.totalSpent.toFixed(2)}`,
            icon: TrendingUp,
          },
          {
            label: "Avg Order",
            value: `$${summary.avgOrderValue.toFixed(2)}`,
            icon: TrendingUp,
          },
          {
            label: "Favourite Cat.",
            value: summary.favoriteCategory || "—",
            icon: Star,
          },
        ].map(({ label, value, icon: Icon }) => (
          <div key={label} className="rounded-xl border bg-card p-4">
            <div className="flex items-center gap-1.5 text-muted-foreground text-xs mb-1">
              <Icon className="h-3.5 w-3.5" /> {label}
            </div>
            <p className="text-xl font-bold">{value}</p>
          </div>
        ))}
      </div>

      {/* Dates */}
      {(summary.firstOrder || summary.lastOrder) && (
        <div className="flex gap-6 mb-6 text-sm text-muted-foreground">
          {summary.firstOrder && (
            <div className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4" />
              First order: {new Date(summary.firstOrder).toLocaleDateString()}
            </div>
          )}
          {summary.lastOrder && (
            <div className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4" />
              Last order: {new Date(summary.lastOrder).toLocaleDateString()}
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b">
        {(["overview", "items", "orders"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors capitalize ${
              activeTab === tab
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab === "overview"
              ? "Category Breakdown"
              : tab === "items"
                ? "Item Breakdown"
                : "Order History"}
          </button>
        ))}
      </div>

      {/* Overview — Category Breakdown */}
      {activeTab === "overview" && (
        <div className="rounded-xl border bg-card overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40 text-muted-foreground text-xs uppercase">
                <th className="px-4 py-3 text-left">Category</th>
                <th className="px-4 py-3 text-right">Qty Purchased</th>
                <th className="px-4 py-3 text-right">Total Spent</th>
                <th className="px-4 py-3 text-left">Top Item</th>
              </tr>
            </thead>
            <tbody>
              {categoryBreakdown.length === 0 ? (
                <tr>
                  <td
                    colSpan={4}
                    className="text-center py-12 text-muted-foreground"
                  >
                    No purchase data yet
                  </td>
                </tr>
              ) : (
                categoryBreakdown.map((cat) => (
                  <tr key={cat.category} className="border-b hover:bg-muted/10">
                    <td className="px-4 py-3 font-medium">{cat.category}</td>
                    <td className="px-4 py-3 text-right">{cat.quantity}</td>
                    <td className="px-4 py-3 text-right">
                      ${cat.totalSpent.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {cat.topItem}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Items — Item Breakdown */}
      {activeTab === "items" && (
        <div className="rounded-xl border bg-card overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40 text-muted-foreground text-xs uppercase">
                <th className="px-4 py-3 text-left">Item</th>
                <th className="px-4 py-3 text-left">Category</th>
                <th className="px-4 py-3 text-right">Qty</th>
                <th className="px-4 py-3 text-right">Total Spent</th>
                <th className="px-4 py-3 text-left">Last Ordered</th>
              </tr>
            </thead>
            <tbody>
              {itemBreakdown.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="text-center py-12 text-muted-foreground"
                  >
                    No purchase data yet
                  </td>
                </tr>
              ) : (
                itemBreakdown.map((item, i) => (
                  <tr key={i} className="border-b hover:bg-muted/10">
                    <td className="px-4 py-3 font-medium">{item.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {item.category}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold">
                      {item.quantity}
                    </td>
                    <td className="px-4 py-3 text-right">
                      ${item.totalSpent.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {item.lastOrdered
                        ? new Date(item.lastOrdered).toLocaleDateString()
                        : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Orders — Order History */}
      {activeTab === "orders" && (
        <div className="space-y-3">
          {orders.length === 0 ? (
            <div className="rounded-xl border bg-card p-12 text-center text-muted-foreground">
              No orders yet
            </div>
          ) : (
            orders.map((order) => {
              const isExpanded = expandedOrderId === order.id;
              return (
                <div
                  key={order.id}
                  className="rounded-xl border bg-card overflow-hidden"
                >
                  <div
                    className="flex items-center gap-3 px-5 py-3 cursor-pointer hover:bg-muted/20"
                    onClick={() =>
                      setExpandedOrderId(isExpanded ? null : order.id)
                    }
                  >
                    <span className="font-mono font-semibold text-sm">
                      {order.id}
                    </span>
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_COLOR[order.status] || "bg-gray-100 text-gray-700"}`}
                    >
                      {order.status.replace(/_/g, " ")}
                    </span>
                    {order.source !== "online" && (
                      <span className="inline-flex rounded-full px-2 py-0.5 text-xs bg-zinc-100 text-zinc-700 capitalize">
                        {order.source}
                      </span>
                    )}
                    <span className="text-sm text-muted-foreground capitalize">
                      {order.orderType}
                    </span>
                    <span className="ml-auto font-semibold">
                      ${order.total.toFixed(2)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(order.createdAt).toLocaleDateString()}
                    </span>
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                  {isExpanded && (
                    <div className="border-t px-5 py-3 bg-muted/10">
                      <div className="space-y-1 text-sm">
                        {order.items.map((item, i) => (
                          <div key={i} className="flex justify-between">
                            <span>
                              {item.quantity}× {item.name}
                            </span>
                            <span>
                              ${(item.price * item.quantity).toFixed(2)}
                            </span>
                          </div>
                        ))}
                        <div className="border-t pt-1 flex justify-between font-bold">
                          <span>Total</span>
                          <span>${order.total.toFixed(2)}</span>
                        </div>
                      </div>
                      <div className="mt-2 flex gap-4 text-xs text-muted-foreground">
                        <span>Branch: {order.branchName || "—"}</span>
                        <span>Payment: {order.paymentMethod}</span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
