import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { UtensilsCrossed, Mail, Lock, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRestaurant } from "@/contexts/RestaurantContext";

// On production domains the host header identifies the tenant automatically.
// On localhost (dev mode only) we expose a restaurant ID field that sends X-Restaurant-ID.
// import.meta.env.DEV is true only during `vite dev`; it is false in `vite build` output,
// so this constant is always false in a production bundle regardless of hostname.
const IS_LOCALHOST =
  import.meta.env.DEV &&
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1");

function isValidAdminToken(token: string | null): boolean {
  if (!token) return false;
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(base64));
    return (
      payload.type === "admin" &&
      typeof payload.exp === "number" &&
      payload.exp > Date.now() / 1000
    );
  } catch {
    return false;
  }
}

export default function AdminLoginPage() {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [devRestaurantId, setDevRestaurantId] = useState("");
  const { restaurantName } = useRestaurant();

  useEffect(() => {
    if (isValidAdminToken(localStorage.getItem("admin_token"))) {
      navigate("/admin/dashboard", { replace: true });
    }
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const form = e.currentTarget;
    const email = (form.elements.namedItem("email") as HTMLInputElement).value;
    const password = (form.elements.namedItem("password") as HTMLInputElement)
      .value;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    // On localhost only: pass X-Restaurant-ID header so the backend resolves the right tenant
    if (IS_LOCALHOST && devRestaurantId) {
      headers["X-Restaurant-ID"] = devRestaurantId;
    }

    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers,
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        setError("Invalid email or password.");
        return;
      }
      const data = await res.json();
      localStorage.setItem("admin_token", data.token);
      localStorage.setItem("admin_user", JSON.stringify(data.admin));
      navigate("/admin/dashboard", { replace: true });
    } catch {
      setError("Connection error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-muted/30 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-primary">
            <UtensilsCrossed className="h-8 w-8 text-primary-foreground" />
          </div>
          <h1 className="font-serif text-2xl font-bold">Admin Portal</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {restaurantName} Management System
          </p>
        </div>

        <div className="rounded-2xl border bg-card p-8 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="admin@example.com"
                  className="pl-10"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  className="pl-10 pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Dev-only: on localhost you must specify which tenant to log into */}
            {IS_LOCALHOST && (
              <div className="space-y-2">
                <Label htmlFor="dev_rid">
                  Restaurant ID{" "}
                  <span className="text-muted-foreground text-xs">
                    (dev only — leave blank for restaurant 1)
                  </span>
                </Label>
                <Input
                  id="dev_rid"
                  type="number"
                  min="1"
                  placeholder="e.g. 2"
                  value={devRestaurantId}
                  onChange={(e) => setDevRestaurantId(e.target.value)}
                />
              </div>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}

            <Button
              type="submit"
              className="w-full"
              size="lg"
              disabled={loading}
            >
              {loading ? "Signing in…" : "Sign In"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
