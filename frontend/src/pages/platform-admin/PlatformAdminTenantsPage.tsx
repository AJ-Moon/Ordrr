import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  Plus,
  Search,
  Eye,
  Trash2,
  Globe,
  ShoppingBag,
  Users,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

interface Tenant {
  id: number;
  name: string;
  slug: string;
  createdAt: string | null;
  domainCount: number;
  adminCount: number;
  orderCount: number;
  primaryDomain: string | null;
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

export default function PlatformAdminTenantsPage() {
  const navigate = useNavigate();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchTenants = () => {
    setLoading(true);
    pFetch("/api/platform-admin/tenants")
      .then((r) => r.json())
      .then(setTenants)
      .catch(() => toast.error("Failed to load tenants"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const filtered = tenants.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.slug.toLowerCase().includes(search.toLowerCase()) ||
      (t.primaryDomain || "").toLowerCase().includes(search.toLowerCase()),
  );

  const handleDelete = async () => {
    if (deleteId == null) return;
    setDeleting(true);
    try {
      const res = await pFetch(`/api/platform-admin/tenants/${deleteId}`, {
        method: "DELETE",
      });
      if (res.ok || res.status === 204) {
        toast.success("Tenant deleted");
        setTenants((prev) => prev.filter((t) => t.id !== deleteId));
      } else {
        const data = await res.json().catch(() => ({}));
        toast.error(data.detail || "Failed to delete tenant");
      }
    } catch {
      toast.error("Network error");
    } finally {
      setDeleting(false);
      setDeleteId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Tenants</h1>
          <p className="text-sm text-slate-400 mt-1">
            {tenants.length} restaurant{tenants.length !== 1 ? "s" : ""} on the
            platform
          </p>
        </div>
        <Button
          onClick={() => navigate("/platform-admin/tenants/new")}
          className="bg-violet-600 hover:bg-violet-700 text-white"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Tenant
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
        <Input
          placeholder="Search by name, slug, or domain…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9 bg-slate-900 border-slate-700 text-white placeholder:text-slate-500 focus:border-violet-500"
        />
      </div>

      {/* Table */}
      <Card className="border-slate-800 bg-slate-900">
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-7 w-7 animate-spin text-slate-400" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-16 text-center text-slate-500 text-sm">
              {search
                ? "No tenants match your search."
                : "No tenants yet. Create one!"}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-slate-800 hover:bg-transparent">
                  <TableHead className="text-slate-400">Restaurant</TableHead>
                  <TableHead className="text-slate-400">
                    Primary Domain
                  </TableHead>
                  <TableHead className="text-slate-400 text-center">
                    <Globe className="h-4 w-4 inline mr-1" />
                    Domains
                  </TableHead>
                  <TableHead className="text-slate-400 text-center">
                    <Users className="h-4 w-4 inline mr-1" />
                    Admins
                  </TableHead>
                  <TableHead className="text-slate-400 text-center">
                    <ShoppingBag className="h-4 w-4 inline mr-1" />
                    Orders
                  </TableHead>
                  <TableHead className="text-slate-400">Created</TableHead>
                  <TableHead className="text-right text-slate-400">
                    Actions
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((t) => (
                  <TableRow
                    key={t.id}
                    className="border-slate-800 hover:bg-slate-800/50"
                  >
                    <TableCell>
                      <div>
                        <p className="font-medium text-white">{t.name}</p>
                        <p className="text-xs text-slate-500 font-mono">
                          {t.slug}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      {t.primaryDomain ? (
                        <Badge
                          variant="outline"
                          className="border-emerald-700 text-emerald-400 bg-emerald-500/10 font-mono text-xs"
                        >
                          {t.primaryDomain}
                        </Badge>
                      ) : (
                        <span className="text-slate-600 text-xs">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-center text-slate-300">
                      {t.domainCount}
                    </TableCell>
                    <TableCell className="text-center text-slate-300">
                      {t.adminCount}
                    </TableCell>
                    <TableCell className="text-center text-slate-300">
                      {t.orderCount}
                    </TableCell>
                    <TableCell className="text-slate-400 text-sm">
                      {t.createdAt
                        ? new Date(t.createdAt).toLocaleDateString()
                        : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link to={`/platform-admin/tenants/${t.id}`}>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-slate-400 hover:text-white hover:bg-slate-700"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        </Link>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-slate-400 hover:text-red-400 hover:bg-red-500/10"
                          onClick={() => setDeleteId(t.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Delete confirmation */}
      <AlertDialog
        open={deleteId != null}
        onOpenChange={(open) => !open && setDeleteId(null)}
      >
        <AlertDialogContent className="bg-slate-900 border-slate-700 text-white">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete tenant?</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-400">
              This will permanently delete the restaurant and ALL its data —
              orders, customers, menu items, branches, settings — everything.
              This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              className="bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700"
              disabled={deleting}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700 text-white"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              {deleting ? "Deleting…" : "Yes, delete permanently"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
