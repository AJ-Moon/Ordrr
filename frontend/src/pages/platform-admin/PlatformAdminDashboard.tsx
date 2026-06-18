import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Building2,
  ShoppingBag,
  Users,
  Globe,
  Loader2,
  TrendingUp,
  ArrowRight,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

interface Stats {
  totalTenants: number;
  totalOrders: number;
  totalCustomers: number;
  totalDomains: number;
  topTenants: { name: string; orders: number }[];
}

function pFetch(url: string) {
  const token = localStorage.getItem("platform_admin_token");
  return fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export default function PlatformAdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    pFetch("/api/platform-admin/stats")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setStats)
      .catch((e) => {
        setError(true);
        toast.error(`Failed to load stats: ${e.message}`);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3">
        <AlertCircle className="h-10 w-10 text-red-400" />
        <p className="text-slate-400 text-sm">Failed to load dashboard stats.</p>
        <p className="text-slate-500 text-xs">Check the backend terminal for errors.</p>
      </div>
    );
  }

  const cards = [
    {
      label: "Total Tenants",
      value: stats?.totalTenants ?? 0,
      icon: Building2,
      color: "text-violet-400",
      bg: "bg-violet-500/10",
    },
    {
      label: "Total Orders",
      value: stats?.totalOrders ?? 0,
      icon: ShoppingBag,
      color: "text-emerald-400",
      bg: "bg-emerald-500/10",
    },
    {
      label: "Total Customers",
      value: stats?.totalCustomers ?? 0,
      icon: Users,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
    },
    {
      label: "Verified Domains",
      value: stats?.totalDomains ?? 0,
      icon: Globe,
      color: "text-amber-400",
      bg: "bg-amber-500/10",
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Platform Dashboard</h1>
        <p className="text-sm text-slate-400 mt-1">
          Overview of all tenants across the platform
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((c) => (
          <Card key={c.label} className="border-slate-800 bg-slate-900">
            <CardContent className="pt-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-slate-400">{c.label}</p>
                  <p className="text-3xl font-bold text-white mt-1">
                    {c.value}
                  </p>
                </div>
                <div className={`rounded-lg p-2 ${c.bg}`}>
                  <c.icon className={`h-5 w-5 ${c.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Top tenants by orders */}
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base text-white">
              <TrendingUp className="h-4 w-4 text-violet-400" />
              Top Tenants by Orders
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(stats?.topTenants ?? []).length === 0 ? (
              <p className="text-sm text-slate-500">No data yet.</p>
            ) : (
              (stats?.topTenants ?? []).map((t, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-slate-500 w-4">
                      #{i + 1}
                    </span>
                    <span className="text-white font-medium">{t.name}</span>
                  </div>
                  <span className="text-slate-400">{t.orders} orders</span>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Quick actions */}
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-white">
              Quick Actions
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Link
              to="/platform-admin/tenants/new"
              className="flex items-center justify-between rounded-lg border border-slate-800 px-4 py-3 text-sm text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
            >
              <span className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-violet-400" />
                Create New Tenant
              </span>
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/platform-admin/tenants"
              className="flex items-center justify-between rounded-lg border border-slate-800 px-4 py-3 text-sm text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
            >
              <span className="flex items-center gap-2">
                <Globe className="h-4 w-4 text-emerald-400" />
                Manage All Tenants
              </span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
