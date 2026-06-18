import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ShoppingBag,
  Users,
  Clock,
  DollarSign,
  MessageSquare,
  UtensilsCrossed,
} from "lucide-react";

interface DashboardData {
  totalOrders: number;
  todayOrders: number;
  pendingOrders: number;
  totalRevenue: number;
  todayRevenue: number;
  totalCustomers: number;
  unreadMessages: number;
  popularItems: { name: string; count: number }[];
  recentOrders: {
    id: string;
    status: string;
    total: number;
    createdAt: string;
    guestName?: string;
  }[];
}

const STATUS_COLORS: Record<string, string> = {
  placed: "bg-blue-100 text-blue-700",
  confirmed: "bg-blue-100 text-blue-700",
  preparing: "bg-amber-100 text-amber-700",
  ready: "bg-amber-100 text-amber-700",
  out_for_delivery: "bg-amber-100 text-amber-700",
  delivered: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
};

export default function AdminDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("admin_token");
    fetch("/api/admin/dashboard", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then(setData)
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading)
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-8 w-36 mb-2" />
          <Skeleton className="h-4 w-56" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="pt-5">
                <Skeleton className="h-20" />
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <Skeleton className="h-5 w-32" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-44" />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <Skeleton className="h-5 w-32" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-44" />
            </CardContent>
          </Card>
        </div>
      </div>
    );
  if (!data)
    return (
      <div className="py-16 text-center text-muted-foreground">
        Failed to load dashboard
      </div>
    );

  const stats = [
    {
      label: "Total Orders",
      value: data.totalOrders,
      icon: ShoppingBag,
      sub: `${data.todayOrders} today`,
    },
    {
      label: "Pending Orders",
      value: data.pendingOrders,
      icon: Clock,
      sub: "Awaiting action",
    },
    {
      label: "Total Revenue",
      value: `$${(data.totalRevenue || 0).toFixed(2)}`,
      icon: DollarSign,
      sub: `$${(data.todayRevenue || 0).toFixed(2)} today`,
    },
    {
      label: "Total Customers",
      value: data.totalCustomers,
      icon: Users,
      sub: "Registered accounts",
    },
    {
      label: "Unread Messages",
      value: data.unreadMessages,
      icon: MessageSquare,
      sub: "Contact form",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-medium">Dashboard</h1>
        <p className="text-muted-foreground text-sm">
          Restaurant overview at a glance
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardContent className="pt-5">
              <p className="text-sm text-muted-foreground">{s.label}</p>
              <p
                className={`text-2xl font-semibold mt-1 ${
                  s.label === "Pending Orders" && (s.value as number) > 0
                    ? "text-primary"
                    : ""
                }`}
              >
                {s.value}
              </p>
              <p className="text-xs text-muted-foreground mt-1">{s.sub}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Orders */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Orders</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(data.recentOrders || []).length === 0 && (
                <p className="text-sm text-muted-foreground">No orders yet.</p>
              )}
              {(data.recentOrders || []).map((o) => (
                <div
                  key={o.id}
                  className="flex items-center justify-between text-sm"
                >
                  <div>
                    <p className="font-mono font-medium">{o.id}</p>
                    <p className="text-xs text-muted-foreground">
                      {o.guestName || "Registered user"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_COLORS[o.status] || ""}`}
                    >
                      {o.status.replace(/_/g, " ")}
                    </span>
                    <span className="font-medium">
                      ${(o.total || 0).toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Popular Items */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Popular Items</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(data.popularItems || []).length === 0 && (
                <p className="text-sm text-muted-foreground">No data yet.</p>
              )}
              {(data.popularItems || []).map((item, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-2">
                    <UtensilsCrossed className="h-4 w-4 text-muted-foreground" />
                    <span>{item.name}</span>
                  </div>
                  <span className="text-xs bg-primary/10 text-primary font-medium px-2 py-0.5 rounded-full">
                    {item.count} orders
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
