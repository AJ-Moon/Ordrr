import { useNavigate, NavLink, Outlet } from "react-router-dom";
import {
  ShieldCheck,
  LayoutDashboard,
  Building2,
  Plus,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  {
    label: "Dashboard",
    to: "/platform-admin/dashboard",
    icon: LayoutDashboard,
  },
  { label: "All Tenants", to: "/platform-admin/tenants", icon: Building2 },
  { label: "New Tenant", to: "/platform-admin/tenants/new", icon: Plus },
];

export default function PlatformAdminLayout() {
  const navigate = useNavigate();

  const adminUser = (() => {
    try {
      return JSON.parse(localStorage.getItem("platform_admin_user") || "{}");
    } catch {
      return {};
    }
  })();

  const handleLogout = () => {
    localStorage.removeItem("platform_admin_token");
    localStorage.removeItem("platform_admin_user");
    navigate("/platform-admin/login", { replace: true });
  };

  return (
    <div className="flex h-screen bg-slate-950 text-white">
      {/* Sidebar */}
      <aside className="flex w-64 flex-col border-r border-slate-800 bg-slate-900">
        {/* Logo */}
        <div className="flex items-center gap-3 border-b border-slate-800 px-6 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-600">
            <ShieldCheck className="h-5 w-5 text-white" />
          </div>
          <div>
            <p className="font-semibold text-sm leading-none text-white">
              Platform Admin
            </p>
            <p className="text-xs text-slate-400 mt-0.5">Super Admin Panel</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map(({ label, to, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to !== "/platform-admin/tenants"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-violet-600 text-white"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white",
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="border-t border-slate-800 px-3 py-4">
          <div className="px-3 py-2 mb-1">
            <p className="text-sm font-medium leading-none text-white">
              {adminUser.name || "Platform Admin"}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              {adminUser.email || ""}
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-400 hover:bg-slate-800 hover:text-red-400 transition-colors"
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-slate-950">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
