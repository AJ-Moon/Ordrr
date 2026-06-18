import { useEffect, useState, useMemo } from "react";
import { useNavigate, Outlet, NavLink } from "react-router-dom";
import {
  UtensilsCrossed,
  ClipboardList,
  CheckCircle2,
  Menu,
  FileText,
  Settings,
  LogOut,
  LayoutDashboard,
  MapPin,
  MessageSquare,
  Star,
  Users,
  Paintbrush,
  Activity,
  BarChart3,
  Swords,
  Lightbulb,
  FlaskConical,
  Rocket,
  Gauge,
  Brain,
  PlugZap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchRestaurantTheme } from "@/contexts/RestaurantContext";

const navItems = [
  { label: "Dashboard", to: "/admin/dashboard", icon: LayoutDashboard },
  { label: "Current Orders", to: "/admin/orders/current", icon: ClipboardList },
  {
    label: "Finished Orders",
    to: "/admin/orders/finished",
    icon: CheckCircle2,
  },
  { label: "Customers", to: "/admin/users", icon: Users },
  { label: "Menu", to: "/admin/menu", icon: Menu },
  { label: "Branches", to: "/admin/branches", icon: MapPin },
  {
    label: "Contact Messages",
    to: "/admin/contact-messages",
    icon: MessageSquare,
  },
  { label: "Rewards", to: "/admin/rewards", icon: Star },
  { label: "Branding", to: "/admin/branding", icon: Paintbrush },
  { label: "Content", to: "/admin/content", icon: FileText },
  { label: "Settings", to: "/admin/settings", icon: Settings },
  { label: "Operations", to: "/admin/operations", icon: Activity },
  { label: "Analytics", to: "/admin/analytics", icon: BarChart3 },
  { label: "Opportunities", to: "/admin/opportunities", icon: Lightbulb },
  { label: "Experiments", to: "/admin/experiments", icon: FlaskConical },
  { label: "Missions", to: "/admin/missions", icon: Rocket },
  { label: "Operational Missions", to: "/admin/operational-missions", icon: Gauge },
  { label: "Advanced Conversion", to: "/admin/advanced-conversion", icon: Brain },
  { label: "Scale & Integrations", to: "/admin/scale-integrations", icon: PlugZap },
  { label: "Competitors", to: "/admin/competitors", icon: Swords },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const [restaurantName, setRestaurantName] = useState("Admin Panel");

  // useMemo so localStorage is parsed once, not on every re-render
  const adminUser = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("admin_user") || "{}");
    } catch {
      return {};
    }
  }, []);

  useEffect(() => {
    const rid = adminUser.restaurantId;
    if (rid) {
      fetchRestaurantTheme(rid).then((t) => {
        if (t.restaurantName) setRestaurantName(t.restaurantName);
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLogout = async () => {
    const token = localStorage.getItem("admin_token");
    if (token) {
      // Best-effort server-side logout acknowledgement
      fetch("/api/admin/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {
        /* ignore network errors — still log out locally */
      });
    }
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    navigate("/admin/login", { replace: true });
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="flex w-64 flex-col border-r bg-card">
        <div className="flex items-center gap-2 border-b px-6 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
            <UtensilsCrossed className="h-5 w-5 text-primary-foreground" />
          </div>
          <div>
            <p className="font-semibold text-sm leading-none">
              {restaurantName}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">Admin Panel</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map(({ label, to, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t px-3 py-4 space-y-2">
          <div className="px-3 py-2">
            <p className="text-sm font-medium leading-none">
              {adminUser.name || "Admin"}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {adminUser.email || ""}
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
