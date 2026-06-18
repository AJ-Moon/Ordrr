import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  ArrowLeft,
  Globe,
  Users,
  Plus,
  Trash2,
  KeyRound,
  Shield,
  Loader2,
  Save,
  Eye,
  EyeOff,
} from "lucide-react";
import { toast } from "sonner";

interface Domain {
  id: number;
  domain: string;
  isPrimary: boolean;
  verified: boolean;
  createdAt: string | null;
}

interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: string;
  createdAt: string | null;
}

interface Tenant {
  id: number;
  name: string;
  slug: string;
  createdAt: string | null;
  domains: Domain[];
  admins: AdminUser[];
}

function pFetch(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem("platform_admin_token");
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
}

export default function PlatformAdminTenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const restaurantId = Number(id);

  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);

  // Edit name
  const [editName, setEditName] = useState("");
  const [savingName, setSavingName] = useState(false);

  // Add domain dialog
  const [addDomainOpen, setAddDomainOpen] = useState(false);
  const [newDomain, setNewDomain] = useState("");
  const [newDomainPrimary, setNewDomainPrimary] = useState(false);
  const [addingDomain, setAddingDomain] = useState(false);

  // Add admin dialog
  const [addAdminOpen, setAddAdminOpen] = useState(false);
  const [newAdminName, setNewAdminName] = useState("");
  const [newAdminEmail, setNewAdminEmail] = useState("");
  const [newAdminPassword, setNewAdminPassword] = useState("");
  const [newAdminRole, setNewAdminRole] = useState("employee");
  const [showNewAdminPw, setShowNewAdminPw] = useState(false);
  const [addingAdmin, setAddingAdmin] = useState(false);

  // Reset password dialog
  const [resetAdminId, setResetAdminId] = useState<string | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [showResetPw, setShowResetPw] = useState(false);
  const [resettingPw, setResettingPw] = useState(false);

  // Delete admin confirm
  const [deleteAdminId, setDeleteAdminId] = useState<string | null>(null);
  const [deletingAdmin, setDeletingAdmin] = useState(false);

  // Remove domain confirm
  const [deleteDomainId, setDeleteDomainId] = useState<number | null>(null);
  const [deletingDomain, setDeletingDomain] = useState(false);

  const reload = () => {
    setLoading(true);
    pFetch(`/api/platform-admin/tenants/${restaurantId}`)
      .then((r) => r.json())
      .then((data) => {
        setTenant(data);
        setEditName(data.name);
      })
      .catch(() => toast.error("Failed to load tenant"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    reload();
  }, [restaurantId]);

  // ─── Save name ────────────────────────────────────────────────────────────
  const saveName = async () => {
    if (!editName.trim()) {
      toast.error("Name cannot be empty");
      return;
    }
    setSavingName(true);
    try {
      const res = await pFetch(`/api/platform-admin/tenants/${restaurantId}`, {
        method: "PUT",
        body: JSON.stringify({ name: editName.trim() }),
      });
      if (res.ok) {
        toast.success("Name updated");
        setTenant((t) => (t ? { ...t, name: editName.trim() } : t));
      } else {
        const d = await res.json().catch(() => ({}));
        toast.error(d.detail || "Failed to update");
      }
    } catch {
      toast.error("Network error");
    } finally {
      setSavingName(false);
    }
  };

  // ─── Add domain ───────────────────────────────────────────────────────────
  const addDomain = async () => {
    const domain = newDomain.trim().toLowerCase();
    if (!domain) {
      toast.error("Enter a domain");
      return;
    }
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/.test(domain)) {
      toast.error("Invalid domain format (e.g. example.com)");
      return;
    }
    setAddingDomain(true);
    try {
      const res = await pFetch(
        `/api/platform-admin/tenants/${restaurantId}/domains`,
        {
          method: "POST",
          body: JSON.stringify({ domain, is_primary: newDomainPrimary }),
        },
      );
      if (res.ok) {
        toast.success("Domain added");
        setAddDomainOpen(false);
        setNewDomain("");
        setNewDomainPrimary(false);
        reload();
      } else {
        const d = await res.json().catch(() => ({}));
        toast.error(d.detail || "Failed to add domain");
      }
    } catch {
      toast.error("Network error");
    } finally {
      setAddingDomain(false);
    }
  };

  // ─── Remove domain ────────────────────────────────────────────────────────
  const removeDomain = async () => {
    if (!deleteDomainId) return;
    setDeletingDomain(true);
    try {
      const res = await pFetch(
        `/api/platform-admin/tenants/${restaurantId}/domains/${deleteDomainId}`,
        { method: "DELETE" },
      );
      if (res.ok) {
        toast.success("Domain removed");
        setTenant((t) =>
          t
            ? {
                ...t,
                domains: t.domains.filter((d) => d.id !== deleteDomainId),
              }
            : t,
        );
      } else {
        const d = await res.json().catch(() => ({}));
        toast.error(d.detail || "Failed to remove domain");
      }
    } catch {
      toast.error("Network error");
    } finally {
      setDeletingDomain(false);
      setDeleteDomainId(null);
    }
  };

  // ─── Add admin ────────────────────────────────────────────────────────────
  const addAdmin = async () => {
    if (!newAdminEmail.trim() || !newAdminPassword || !newAdminName.trim()) {
      toast.error("Name, email and password are required");
      return;
    }
    if (newAdminPassword.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    setAddingAdmin(true);
    try {
      const res = await pFetch(
        `/api/platform-admin/tenants/${restaurantId}/add-admin`,
        {
          method: "POST",
          body: JSON.stringify({
            email: newAdminEmail.trim(),
            password: newAdminPassword,
            name: newAdminName.trim(),
            role: newAdminRole,
          }),
        },
      );
      if (res.ok) {
        toast.success("Admin user created");
        setAddAdminOpen(false);
        setNewAdminName("");
        setNewAdminEmail("");
        setNewAdminPassword("");
        setNewAdminRole("employee");
        reload();
      } else {
        const d = await res.json().catch(() => ({}));
        toast.error(d.detail || "Failed to add admin");
      }
    } catch {
      toast.error("Network error");
    } finally {
      setAddingAdmin(false);
    }
  };

  // ─── Reset password ───────────────────────────────────────────────────────
  const resetPw = async () => {
    if (!resetAdminId || !resetPassword) {
      toast.error("Enter a new password");
      return;
    }
    if (resetPassword.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    setResettingPw(true);
    try {
      const res = await pFetch(
        `/api/platform-admin/tenants/${restaurantId}/reset-admin`,
        {
          method: "POST",
          body: JSON.stringify({
            admin_id: resetAdminId,
            new_password: resetPassword,
          }),
        },
      );
      if (res.ok) {
        toast.success("Password reset successfully");
        setResetAdminId(null);
        setResetPassword("");
      } else {
        const d = await res.json().catch(() => ({}));
        toast.error(d.detail || "Failed to reset password");
      }
    } catch {
      toast.error("Network error");
    } finally {
      setResettingPw(false);
    }
  };

  // ─── Delete admin ─────────────────────────────────────────────────────────
  const deleteAdmin = async () => {
    if (!deleteAdminId) return;
    setDeletingAdmin(true);
    try {
      const res = await pFetch(
        `/api/platform-admin/tenants/${restaurantId}/admins/${deleteAdminId}`,
        { method: "DELETE" },
      );
      if (res.ok || res.status === 204) {
        toast.success("Admin removed");
        setTenant((t) =>
          t
            ? { ...t, admins: t.admins.filter((a) => a.id !== deleteAdminId) }
            : t,
        );
      } else {
        const d = await res.json().catch(() => ({}));
        toast.error(d.detail || "Failed to remove admin");
      }
    } catch {
      toast.error("Network error");
    } finally {
      setDeletingAdmin(false);
      setDeleteAdminId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (!tenant) {
    return (
      <div className="text-center py-24">
        <p className="text-slate-400">Tenant not found.</p>
        <Link to="/platform-admin/tenants">
          <Button
            variant="ghost"
            className="mt-4 text-slate-400 hover:text-white"
          >
            Back to Tenants
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/platform-admin/tenants">
          <Button
            variant="ghost"
            size="icon"
            className="text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white">{tenant.name}</h1>
          <p className="text-sm text-slate-400 mt-0.5 font-mono">
            ID #{tenant.id} · slug: {tenant.slug}
          </p>
        </div>
      </div>

      {/* Edit name */}
      <Card className="border-slate-800 bg-slate-900">
        <CardHeader className="pb-3">
          <CardTitle className="text-white text-base">
            Restaurant Name
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <div className="flex-1 space-y-1.5">
              <Label className="text-slate-400 text-xs">Display Name</Label>
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="bg-slate-800 border-slate-700 text-white focus:border-violet-500"
              />
            </div>
            <Button
              onClick={saveName}
              disabled={savingName || editName.trim() === tenant.name}
              className="bg-violet-600 hover:bg-violet-700 text-white"
            >
              {savingName ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              <span className="ml-2">Save</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Domains */}
      <Card className="border-slate-800 bg-slate-900">
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="text-white text-base flex items-center gap-2">
              <Globe className="h-4 w-4 text-emerald-400" />
              Domains ({tenant.domains.length})
            </CardTitle>
            <CardDescription className="text-slate-400">
              Domains mapped to this restaurant
            </CardDescription>
          </div>
          <Button
            size="sm"
            onClick={() => setAddDomainOpen(true)}
            className="bg-violet-600 hover:bg-violet-700 text-white"
          >
            <Plus className="h-4 w-4 mr-1" />
            Add Domain
          </Button>
        </CardHeader>
        <CardContent>
          {tenant.domains.length === 0 ? (
            <p className="text-slate-500 text-sm">
              No domains configured. Add one to map traffic.
            </p>
          ) : (
            <div className="space-y-2">
              {tenant.domains.map((d) => (
                <div
                  key={d.id}
                  className="flex items-center justify-between rounded-lg border border-slate-800 px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm text-white">
                      {d.domain}
                    </span>
                    <div className="flex items-center gap-1.5">
                      {d.isPrimary && (
                        <Badge className="bg-violet-500/20 text-violet-400 border-violet-600 text-xs">
                          Primary
                        </Badge>
                      )}
                      {d.verified && (
                        <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-700 text-xs">
                          Verified
                        </Badge>
                      )}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-slate-500 hover:text-red-400 hover:bg-red-500/10"
                    onClick={() => setDeleteDomainId(d.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Admin users */}
      <Card className="border-slate-800 bg-slate-900">
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="text-white text-base flex items-center gap-2">
              <Users className="h-4 w-4 text-blue-400" />
              Admin Users ({tenant.admins.length})
            </CardTitle>
            <CardDescription className="text-slate-400">
              Users who can access the restaurant admin panel
            </CardDescription>
          </div>
          <Button
            size="sm"
            onClick={() => setAddAdminOpen(true)}
            className="bg-violet-600 hover:bg-violet-700 text-white"
          >
            <Plus className="h-4 w-4 mr-1" />
            Add Admin
          </Button>
        </CardHeader>
        <CardContent>
          {tenant.admins.length === 0 ? (
            <p className="text-slate-500 text-sm">
              No admin users. Add one to allow login.
            </p>
          ) : (
            <div className="space-y-2">
              {tenant.admins.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between rounded-lg border border-slate-800 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-white">{a.name}</p>
                    <p className="text-xs text-slate-400">{a.email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge
                      className={
                        a.role === "admin"
                          ? "bg-violet-500/20 text-violet-400 border-violet-700 text-xs"
                          : "bg-slate-700 text-slate-300 border-slate-600 text-xs"
                      }
                    >
                      <Shield className="h-3 w-3 mr-1" />
                      {a.role}
                    </Badge>
                    <Button
                      size="sm"
                      variant="ghost"
                      title="Reset password"
                      className="text-slate-500 hover:text-amber-400 hover:bg-amber-500/10"
                      onClick={() => {
                        setResetAdminId(a.id);
                        setResetPassword("");
                        setShowResetPw(false);
                      }}
                    >
                      <KeyRound className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      title="Remove admin"
                      className="text-slate-500 hover:text-red-400 hover:bg-red-500/10"
                      onClick={() => setDeleteAdminId(a.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Dialogs ── */}

      {/* Add domain */}
      <Dialog open={addDomainOpen} onOpenChange={setAddDomainOpen}>
        <DialogContent className="sm:max-w-lg bg-slate-900 border-slate-700 text-white">
          <DialogHeader>
            <DialogTitle>Add Domain</DialogTitle>
            <DialogDescription className="text-slate-400">
              Enter the domain to map to this restaurant.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-slate-300">Domain</Label>
              <Input
                placeholder="burgerpalace.com"
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                className="bg-slate-800 border-slate-700 text-white focus:border-violet-500"
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={newDomainPrimary}
                onChange={(e) => setNewDomainPrimary(e.target.checked)}
                className="accent-violet-500"
              />
              <span className="text-sm text-slate-300">
                Set as primary domain
              </span>
            </label>
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              className="text-slate-400 hover:text-white"
              onClick={() => setAddDomainOpen(false)}
              disabled={addingDomain}
            >
              Cancel
            </Button>
            <Button
              onClick={addDomain}
              disabled={addingDomain}
              className="bg-violet-600 hover:bg-violet-700 text-white"
            >
              {addingDomain ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              Add Domain
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add admin */}
      <Dialog open={addAdminOpen} onOpenChange={setAddAdminOpen}>
        <DialogContent className="sm:max-w-lg bg-slate-900 border-slate-700 text-white">
          <DialogHeader>
            <DialogTitle>Add Admin User</DialogTitle>
            <DialogDescription className="text-slate-400">
              Create a new admin account for this restaurant.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {[
              {
                label: "Name",
                value: newAdminName,
                set: setNewAdminName,
                placeholder: "Jane Doe",
              },
              {
                label: "Email",
                value: newAdminEmail,
                set: setNewAdminEmail,
                placeholder: "jane@burgerpalace.com",
              },
            ].map((f) => (
              <div key={f.label} className="space-y-1.5">
                <Label className="text-slate-300">{f.label}</Label>
                <Input
                  placeholder={f.placeholder}
                  value={f.value}
                  onChange={(e) => f.set(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white focus:border-violet-500"
                />
              </div>
            ))}
            <div className="space-y-1.5">
              <Label className="text-slate-300">Password</Label>
              <div className="relative">
                <Input
                  type={showNewAdminPw ? "text" : "password"}
                  placeholder="Min. 8 characters"
                  value={newAdminPassword}
                  onChange={(e) => setNewAdminPassword(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white focus:border-violet-500 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowNewAdminPw((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                  tabIndex={-1}
                >
                  {showNewAdminPw ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-slate-300">Role</Label>
              <select
                value={newAdminRole}
                onChange={(e) => setNewAdminRole(e.target.value)}
                className="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-violet-500 focus:outline-none"
              >
                <option value="admin">admin</option>
                <option value="employee">employee</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              className="text-slate-400 hover:text-white"
              onClick={() => setAddAdminOpen(false)}
              disabled={addingAdmin}
            >
              Cancel
            </Button>
            <Button
              onClick={addAdmin}
              disabled={addingAdmin}
              className="bg-violet-600 hover:bg-violet-700 text-white"
            >
              {addingAdmin ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              Create Admin
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reset password */}
      <Dialog
        open={resetAdminId != null}
        onOpenChange={(open) => !open && setResetAdminId(null)}
      >
        <DialogContent className="sm:max-w-lg bg-slate-900 border-slate-700 text-white">
          <DialogHeader>
            <DialogTitle>Reset Admin Password</DialogTitle>
            <DialogDescription className="text-slate-400">
              Enter a new password for this admin user. Min. 8 characters.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label className="text-slate-300">New Password</Label>
            <div className="relative">
              <Input
                type={showResetPw ? "text" : "password"}
                placeholder="Min. 8 characters"
                value={resetPassword}
                onChange={(e) => setResetPassword(e.target.value)}
                className="bg-slate-800 border-slate-700 text-white focus:border-violet-500 pr-10"
              />
              <button
                type="button"
                onClick={() => setShowResetPw((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                tabIndex={-1}
              >
                {showResetPw ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              className="text-slate-400 hover:text-white"
              onClick={() => setResetAdminId(null)}
              disabled={resettingPw}
            >
              Cancel
            </Button>
            <Button
              onClick={resetPw}
              disabled={resettingPw}
              className="bg-amber-600 hover:bg-amber-700 text-white"
            >
              {resettingPw ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              Reset Password
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete admin confirm */}
      <AlertDialog
        open={deleteAdminId != null}
        onOpenChange={(open) => !open && setDeleteAdminId(null)}
      >
        <AlertDialogContent className="bg-slate-900 border-slate-700 text-white">
          <AlertDialogHeader>
            <AlertDialogTitle>Remove admin user?</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-400">
              This admin will lose access to the restaurant panel immediately.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              className="bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700"
              disabled={deletingAdmin}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700 text-white"
              onClick={deleteAdmin}
              disabled={deletingAdmin}
            >
              {deletingAdmin ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Remove domain confirm */}
      <AlertDialog
        open={deleteDomainId != null}
        onOpenChange={(open) => !open && setDeleteDomainId(null)}
      >
        <AlertDialogContent className="bg-slate-900 border-slate-700 text-white">
          <AlertDialogHeader>
            <AlertDialogTitle>Remove domain?</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-400">
              Traffic from this domain will no longer be routed to this
              restaurant.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              className="bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700"
              disabled={deletingDomain}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700 text-white"
              onClick={removeDomain}
              disabled={deletingDomain}
            >
              {deletingDomain ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
