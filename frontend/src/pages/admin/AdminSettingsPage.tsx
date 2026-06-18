import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Save, Info } from "lucide-react";
import { SearchBox } from "@mapbox/search-js-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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

function RestaurantStatusCard() {
  const [restaurantOpen, setRestaurantOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    adminFetch("/api/admin/settings")
      .then((r) => (r.ok ? r.json() : {}))
      .then((d: Record<string, string>) => {
        setRestaurantOpen(
          String(d.restaurant_open ?? "true").toLowerCase() === "true",
        );
      })
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    const res = await adminFetch("/api/admin/settings", {
      method: "PUT",
      body: JSON.stringify({
        restaurant_open: restaurantOpen ? "true" : "false",
      }),
    });
    if (res.ok) {
      try {
        localStorage.removeItem("restaurant_theme_cache");
      } catch {
        /* ignore */
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <div className="mb-6 rounded-xl border bg-card p-5">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-2">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-72" />
          </div>
          <Skeleton className="h-8 w-14" />
        </div>
      </div>
    );
  }

  return (
    <div className="mb-6 rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Restaurant Status</h2>
          <p className="text-sm text-muted-foreground">
            {restaurantOpen
              ? "Customers can place orders normally."
              : "Customers will see a 'We are currently closed' banner"}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`text-sm font-medium ${restaurantOpen ? "text-emerald-600" : "text-red-600"}`}
          >
            {restaurantOpen ? "Open" : "Closed"}
          </span>
          <div className="scale-125">
            <Switch
              checked={restaurantOpen}
              onCheckedChange={setRestaurantOpen}
              aria-label="Toggle restaurant open status"
            />
          </div>
        </div>
      </div>

      <div className="mt-4">
        <Button onClick={save} disabled={saving}>
          <Save className="mr-2 h-4 w-4" />
          {saving ? "Saving…" : saved ? "Saved!" : "Save Status"}
        </Button>
      </div>
    </div>
  );
}

function StoreSettingsTab() {
  const [announcement, setAnnouncement] = useState("");
  const [announcementActive, setAnnouncementActive] = useState(false);
  const [deliveryCharge, setDeliveryCharge] = useState("0");
  const [minOrderAmount, setMinOrderAmount] = useState("0");
  const [pointsPerDollar, setPointsPerDollar] = useState("10");
  const [minRedeemPoints, setMinRedeemPoints] = useState("100");
  const [pointsValueCents, setPointsValueCents] = useState("1");
  const [cashOnDelivery, setCashOnDelivery] = useState(true);
  const [maxPointsDiscountPercent, setMaxPointsDiscountPercent] =
    useState("20");
  const [pointsExpiryMonths, setPointsExpiryMonths] = useState("12");
  const [rewardsEnabled, setRewardsEnabled] = useState(true);
  const [deliveryRadiusKm, setDeliveryRadiusKm] = useState("5");
  const [restaurantLat, setRestaurantLat] = useState("");
  const [restaurantLng, setRestaurantLng] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    adminFetch("/api/admin/settings")
      .then((r) => (r.ok ? r.json() : {}))
      .then((d: Record<string, string>) => {
        setAnnouncement(d.announcement ?? "");
        setAnnouncementActive(
          String(d.announcement_active ?? "false").toLowerCase() === "true",
        );
        setDeliveryCharge(d.delivery_charge ?? "0");
        setMinOrderAmount(d.min_order_amount ?? "0");
        setCashOnDelivery(
          String(d.cash_on_delivery ?? "true").toLowerCase() === "true",
        );
        setPointsPerDollar(d.points_per_dollar ?? "10");
        setMinRedeemPoints(d.min_redeem_points ?? "100");
        setPointsValueCents(d.points_value_cents ?? "1");
        setMaxPointsDiscountPercent(d.max_points_discount_percent ?? "20");
        setPointsExpiryMonths(d.points_expiry_months ?? "12");
        setRewardsEnabled(
          String(d.rewards_enabled ?? "true").toLowerCase() === "true",
        );
        setDeliveryRadiusKm(d.delivery_radius_km ?? "5");
        setRestaurantLat(d.restaurant_lat ?? "");
        setRestaurantLng(d.restaurant_lng ?? "");
      })
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    const res = await adminFetch("/api/admin/settings", {
      method: "PUT",
      body: JSON.stringify({
        announcement: announcement.trim(),
        announcement_active: announcementActive ? "true" : "false",
        delivery_charge: String(
          Math.max(0, Number.parseFloat(deliveryCharge || "0") || 0),
        ),
        min_order_amount: String(
          Math.max(0, Number.parseFloat(minOrderAmount || "0") || 0),
        ),
        cash_on_delivery: cashOnDelivery ? "true" : "false",
        points_per_dollar: String(
          Math.max(0, Number.parseInt(pointsPerDollar || "10", 10) || 0),
        ),
        min_redeem_points: String(
          Math.max(1, Number.parseInt(minRedeemPoints || "100", 10) || 100),
        ),
        points_value_cents: String(
          Math.max(0, Number.parseInt(pointsValueCents || "1", 10) || 0),
        ),
        max_points_discount_percent: String(
          Math.min(
            100,
            Math.max(
              0,
              Number.parseInt(maxPointsDiscountPercent || "20", 10) || 20,
            ),
          ),
        ),
        points_expiry_months: String(
          Math.max(1, Number.parseInt(pointsExpiryMonths || "12", 10) || 12),
        ),
        rewards_enabled: rewardsEnabled ? "true" : "false",
        delivery_radius_km: String(
          Math.max(1, Math.min(50, Number.parseFloat(deliveryRadiusKm || "5") || 5)),
        ),
        restaurant_lat: restaurantLat,
        restaurant_lng: restaurantLng,
      }),
    });
    if (res.ok) {
      try {
        localStorage.removeItem("restaurant_theme_cache");
      } catch {
        /* ignore */
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <div className="max-w-xl space-y-4">
        <div className="space-y-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-10 w-full" />
        </div>
        <div className="flex items-center justify-between rounded-lg border p-4">
          <Skeleton className="h-4 w-56" />
          <Skeleton className="h-6 w-12" />
        </div>
        <Skeleton className="h-10 w-32" />
      </div>
    );
  }

  return (
    <div className="max-w-xl space-y-4">
      <div className="space-y-2">
        <Label htmlFor="announcement-banner">Announcement Banner</Label>
        <Input
          id="announcement-banner"
          value={announcement}
          maxLength={120}
          onChange={(e) => setAnnouncement(e.target.value)}
          placeholder="e.g. Free delivery on orders above $25 today"
        />
        <p className="text-xs text-muted-foreground">
          {announcement.length}/120
        </p>
      </div>

      <div className="flex items-center justify-between rounded-lg border p-4">
        <Label htmlFor="announcement-active">
          Shown as a top bar above the navbar
        </Label>
        <Switch
          id="announcement-active"
          checked={announcementActive}
          onCheckedChange={setAnnouncementActive}
        />
      </div>

      <div className="rounded-lg border p-4 space-y-4">
        <h3 className="text-sm font-semibold text-foreground">Ordering</h3>
        <div className="space-y-2">
          <Label htmlFor="delivery-charge">Delivery charge ($)</Label>
          <Input
            id="delivery-charge"
            type="number"
            min="0"
            step="0.01"
            value={deliveryCharge}
            onChange={(e) => setDeliveryCharge(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="min-order-amount">Minimum order amount ($)</Label>
          <Input
            id="min-order-amount"
            type="number"
            min="0"
            step="0.01"
            value={minOrderAmount}
            onChange={(e) => setMinOrderAmount(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="delivery-radius">Delivery radius (km)</Label>
          <Input
            id="delivery-radius"
            type="number"
            min="1"
            max="50"
            step="0.1"
            value={deliveryRadiusKm}
            onChange={(e) => setDeliveryRadiusKm(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">Customers outside this radius will only see pickup option.</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="restaurant-location">Restaurant Location (Mapbox)</Label>
          <div className="relative z-50">
            <SearchBox
              accessToken={import.meta.env.VITE_MAPBOX_TOKEN || ""}
              options={{ language: "en" }}
              onRetrieve={(res) => {
                const feature = res.features[0];
                if (feature) {
                  setRestaurantLng(feature.geometry.coordinates[0].toString());
                  setRestaurantLat(feature.geometry.coordinates[1].toString());
                  toast.success("Location set! Don't forget to click Save Changes.");
                }
              }}
            />
          </div>
          {restaurantLat && restaurantLng && (
            <p className="text-xs text-muted-foreground mt-1">
              Coordinates set: {restaurantLat}, {restaurantLng}
            </p>
          )}
        </div>
        <div className="flex items-center justify-between rounded-lg border p-3 mt-4">
          <Label htmlFor="cash-on-delivery">Enable Cash on Delivery</Label>
          <Switch
            id="cash-on-delivery"
            checked={cashOnDelivery}
            onCheckedChange={setCashOnDelivery}
          />
        </div>
      </div>

      <div className="rounded-lg border p-4 space-y-4">
        <h3 className="text-sm font-semibold text-foreground">
          Rewards Program
        </h3>

        <div className="space-y-2">
          <Label htmlFor="points-per-dollar">Points per dollar spent</Label>
          <Input
            id="points-per-dollar"
            type="number"
            min="0"
            step="1"
            value={pointsPerDollar}
            onChange={(e) => setPointsPerDollar(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="min-redeem-points">Minimum points to redeem</Label>
          <Input
            id="min-redeem-points"
            type="number"
            min="1"
            step="1"
            value={minRedeemPoints}
            onChange={(e) => setMinRedeemPoints(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="points-value-cents">
            Points value (cents per point)
          </Label>
          <Input
            id="points-value-cents"
            type="number"
            min="0"
            step="1"
            value={pointsValueCents}
            onChange={(e) => setPointsValueCents(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="max-points-discount">Max points discount (%)</Label>
          <Input
            id="max-points-discount"
            type="number"
            min="0"
            max="100"
            step="1"
            value={maxPointsDiscountPercent}
            onChange={(e) => setMaxPointsDiscountPercent(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="points-expiry-months">Points expiry (months)</Label>
          <Input
            id="points-expiry-months"
            type="number"
            min="1"
            step="1"
            value={pointsExpiryMonths}
            onChange={(e) => setPointsExpiryMonths(e.target.value)}
          />
        </div>

        <div className="flex items-center justify-between rounded-lg border p-3">
          <Label htmlFor="rewards-enabled">Enable rewards program</Label>
          <Switch
            id="rewards-enabled"
            checked={rewardsEnabled}
            onCheckedChange={setRewardsEnabled}
          />
        </div>
      </div>

      <Button onClick={save} disabled={saving}>
        <Save className="mr-2 h-4 w-4" />
        {saving ? "Saving…" : saved ? "Saved!" : "Save Changes"}
      </Button>
    </div>
  );
}

// ── Contact & Social tab ─────────────────────────────────────────────────────
function SettingsTab({
  fields,
  labels,
}: {
  fields: string[];
  labels: Record<string, string>;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    adminFetch("/api/admin/settings")
      .then((r) => (r.ok ? r.json() : {}))
      .then((d: Record<string, string>) => {
        const filtered: Record<string, string> = {};
        fields.forEach((f) => {
          filtered[f] = d[f] ?? "";
        });
        setValues(filtered);
        setLoading(false);
      });
  }, []);

  const save = async () => {
    if (fields.includes("address") && (!values.address || !values.address.trim())) {
      toast.error("Address is required.");
      return;
    }
    setSaving(true);
    const res = await adminFetch("/api/admin/settings", {
      method: "PUT",
      body: JSON.stringify(values),
    });
    if (res.ok) {
      try {
        localStorage.removeItem("restaurant_theme_cache");
      } catch {
        /* ignore */
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
    setSaving(false);
  };

  if (loading)
    return (
      <div className="max-w-xl space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-10 w-full" />
          </div>
        ))}
        <Skeleton className="h-10 w-32" />
      </div>
    );

  return (
    <div className="max-w-xl space-y-4">
      {fields.map((f) => (
        <div key={f} className="space-y-2">
          <Label>
            {labels[f] ?? f}
            {f === "address" && <span className="text-destructive ml-1">*</span>}
          </Label>
          <Input
            value={values[f] ?? ""}
            onChange={(e) => setValues((p) => ({ ...p, [f]: e.target.value }))}
          />
        </div>
      ))}
      <Button onClick={save} disabled={saving}>
        <Save className="mr-2 h-4 w-4" />
        {saving ? "Saving…" : saved ? "Saved!" : "Save Changes"}
      </Button>
    </div>
  );
}

// ── Branches tab ─────────────────────────────────────────────────────────────
interface Branch {
  id: number;
  name: string;
  address: string;
  city: string;
  phone: string;
  hours: string;
  isOpen: boolean;
}
const EMPTY_BRANCH = {
  name: "",
  address: "",
  city: "",
  phone: "",
  hours: "",
  isOpen: true,
};

function BranchesTab() {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Branch | null>(null);
  const [form, setForm] = useState(EMPTY_BRANCH);
  const [saving, setSaving] = useState(false);

  const fetch_ = async () => {
    setLoading(true);
    try {
      const res = await adminFetch("/api/admin/branches");
      if (res.ok) setBranches(await res.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch_();
  }, []);

  const openAdd = () => {
    setEditing(null);
    setForm(EMPTY_BRANCH);
    setOpen(true);
  };
  const openEdit = (b: Branch) => {
    setEditing(b);
    setForm({
      name: b.name,
      address: b.address,
      city: b.city,
      phone: b.phone,
      hours: b.hours,
      isOpen: b.isOpen,
    });
    setOpen(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      const url = editing
        ? `/api/admin/branches/${editing.id}`
        : "/api/admin/branches";
      const method = editing ? "PUT" : "POST";
      const res = await adminFetch(url, { method, body: JSON.stringify(form) });
      if (res.ok) {
        const saved = await res.json();
        setBranches((prev) =>
          editing
            ? prev.map((b) => (b.id === editing.id ? saved : b))
            : [...prev, saved],
        );
        setOpen(false);
      }
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: number) => {
    if (!confirm("Delete this branch?")) return;
    await adminFetch(`/api/admin/branches/${id}`, { method: "DELETE" });
    setBranches((prev) => prev.filter((b) => b.id !== id));
  };

  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((p) => ({ ...p, [k]: v }));

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button onClick={openAdd}>
          <Plus className="mr-2 h-4 w-4" /> Add Branch
        </Button>
      </div>
      <div className="rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>City</TableHead>
              <TableHead>Phone</TableHead>
              <TableHead>Hours</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <Skeleton className="h-5 w-32" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-20" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-24" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-32" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-14" />
                    </TableCell>
                    <TableCell className="text-right">
                      <Skeleton className="h-8 w-16 ml-auto" />
                    </TableCell>
                  </TableRow>
                ))
              : branches.map((b) => (
                  <TableRow key={b.id}>
                    <TableCell>
                      <div className="font-medium">{b.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {b.address}
                      </div>
                    </TableCell>
                    <TableCell>{b.city}</TableCell>
                    <TableCell>{b.phone}</TableCell>
                    <TableCell className="text-sm">{b.hours}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${b.isOpen ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}
                      >
                        {b.isOpen ? "Open" : "Closed"}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => openEdit(b)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={() => remove(b.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Branch" : "Add Branch"}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="space-y-2">
              <Label>Name <span className="text-destructive">*</span></Label>
              <Input
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Address <span className="text-destructive">*</span></Label>
              <Input
                value={form.address}
                onChange={(e) => set("address", e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>City <span className="text-destructive">*</span></Label>
                <Input
                  value={form.city}
                  onChange={(e) => set("city", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Phone <span className="text-destructive">*</span></Label>
                <Input
                  value={form.phone}
                  onChange={(e) => set("phone", e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Hours</Label>
              <Input
                value={form.hours}
                onChange={(e) => set("hours", e.target.value)}
                placeholder="Mon–Fri 9AM–10PM"
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <Checkbox
                checked={form.isOpen}
                onCheckedChange={(v) => set("isOpen", !!v)}
              />
              <span className="text-sm">Currently Open</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={save} disabled={saving || !form.name.trim() || !form.address.trim() || !form.city.trim() || !form.phone.trim()}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function AdminSettingsPage() {
  const [showGuide, setShowGuide] = useState(true);

  useEffect(() => {
    const dismissed =
      localStorage.getItem("admin_settings_guide_dismissed") === "true";
    if (dismissed) setShowGuide(false);
  }, []);

  return (
    <div className="p-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-sm text-muted-foreground">
            Manage contact info, social links, store settings, and branches
          </p>
        </div>
        {!showGuide && (
          <Button
            variant="outline"
            onClick={() => {
              localStorage.removeItem("admin_settings_guide_dismissed");
              setShowGuide(true);
            }}
          >
            Show Setup Guide
          </Button>
        )}
      </div>

      {showGuide && (
        <div className="mb-6 rounded-xl border bg-muted/30 p-4">
          <div className="mb-3 flex items-start justify-between gap-4">
            <div className="flex items-start gap-2">
              <Info className="mt-0.5 h-4 w-4 text-primary" />
              <div>
                <h2 className="text-sm font-semibold">Settings Setup Guide</h2>
                <p className="text-xs text-muted-foreground">
                  Configure these tabs in order so your store details and
                  operations are complete.
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                localStorage.setItem("admin_settings_guide_dismissed", "true");
                setShowGuide(false);
              }}
            >
              Dismiss
            </Button>
          </div>
          <ol className="ml-5 list-decimal space-y-1 text-sm text-foreground">
            <li>
              Complete Contact Info so customers can call, email, and find your
              location.
            </li>
            <li>Add Social Media links only for channels you actively use.</li>
            <li>
              In Store settings, set announcement, delivery charge, minimum
              order, and rewards values.
            </li>
            <li>
              Set Restaurant Status (open/closed) before business hours change.
            </li>
            <li>
              Add all branch locations and verify hours/phone for each branch.
            </li>
          </ol>
        </div>
      )}

      <RestaurantStatusCard />

      <Tabs defaultValue="contact">
        <TabsList className="mb-6">
          <TabsTrigger value="contact">Contact Info</TabsTrigger>
          <TabsTrigger value="social">Social Media</TabsTrigger>
          <TabsTrigger value="store">Store</TabsTrigger>
          <TabsTrigger value="branches">Locations</TabsTrigger>
        </TabsList>
        <TabsContent value="contact">
          <SettingsTab
            fields={["phone", "email", "address", "hours"]}
            labels={{
              phone: "Phone",
              email: "Email",
              address: "Address",
              hours: "Business Hours",
            }}
          />
        </TabsContent>
        <TabsContent value="social">
          <SettingsTab
            fields={[
              "instagram_url",
              "facebook_url",
              "twitter_url",
              "tiktok_url",
              "youtube_url",
            ]}
            labels={{
              instagram_url: "Instagram URL",
              facebook_url: "Facebook URL",
              twitter_url: "Twitter / X URL",
              tiktok_url: "TikTok URL",
              youtube_url: "YouTube URL",
            }}
          />
        </TabsContent>
        <TabsContent value="store">
          <StoreSettingsTab />
        </TabsContent>
        <TabsContent value="branches">
          <BranchesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
