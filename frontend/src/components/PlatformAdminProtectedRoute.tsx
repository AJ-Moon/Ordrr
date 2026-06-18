import { useEffect, useState } from "react";
import { Outlet, Navigate } from "react-router-dom";
import { Loader2 } from "lucide-react";

export default function PlatformAdminProtectedRoute() {
  const [status, setStatus] = useState<"loading" | "ok" | "unauth">("loading");

  useEffect(() => {
    const token = localStorage.getItem("platform_admin_token");
    if (!token) {
      setStatus("unauth");
      return;
    }
    fetch("/api/platform-admin/me", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => setStatus(r.ok ? "ok" : "unauth"))
      .catch(() => setStatus("unauth"));
  }, []);

  if (status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (status === "unauth") {
    return <Navigate to="/platform-admin/login" replace />;
  }

  return <Outlet />;
}
