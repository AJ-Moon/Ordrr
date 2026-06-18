import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Pencil, Trash2, Plus, Loader2, CheckCircle2, ExternalLink } from "lucide-react";
import { toast } from "sonner";

interface Competitor {
  id: number;
  name: string;
  website: string | null;
  address: string | null;
  notes: string | null;
  currency: string;
  referenceItemName: string | null;
  referencePriceCents: number | null;
  observedAt: string | null;
  status: "active" | "archived";
  verifiedAt: string | null;
  verifiedBy: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

type FormState = {
  name: string;
  website: string;
  address: string;
  notes: string;
  currency: string;
  referenceItemName: string;
  referencePrice: string;
  status: "active" | "archived";
};

const EMPTY_FORM: FormState = {
  name: "",
  website: "",
  address: "",
  notes: "",
  currency: "USD",
  referenceItemName: "",
  referencePrice: "",
  status: "active",
};

function headers() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("admin_token") || ""}`,
  };
}

function money(cents: number | null, currency: string) {
  if (cents == null) return "—";
  return `${currency} ${(cents / 100).toFixed(2)}`;
}

const STALE_DAYS = 90;

function isStale(verifiedAt: string | null) {
  if (!verifiedAt) return true;
  const ageMs = Date.now() - new Date(verifiedAt).getTime();
  return ageMs > STALE_DAYS * 24 * 60 * 60 * 1000;
}

export default function AdminCompetitorsPage() {
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editId, setEditId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/competitors", { headers: headers() });
      if (!res.ok) throw new Error();
      setCompetitors(await res.json());
    } catch {
      toast.error("Could not load competitors");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const openAdd = () => {
    setForm(EMPTY_FORM);
    setEditId(null);
    setDialogOpen(true);
  };

  const openEdit = (c: Competitor) => {
    setForm({
      name: c.name,
      website: c.website || "",
      address: c.address || "",
      notes: c.notes || "",
      currency: c.currency,
      referenceItemName: c.referenceItemName || "",
      referencePrice: c.referencePriceCents != null ? (c.referencePriceCents / 100).toFixed(2) : "",
      status: c.status,
    });
    setEditId(c.id);
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error("Name is required");
      return;
    }
    setSaving(true);
    try {
      const body = JSON.stringify({
        name: form.name.trim(),
        website: form.website.trim() || null,
        address: form.address.trim() || null,
        notes: form.notes.trim() || null,
        currency: form.currency.trim().toUpperCase() || "USD",
        referenceItemName: form.referenceItemName.trim() || null,
        referencePriceCents: form.referencePrice.trim() === "" ? null : Math.round(parseFloat(form.referencePrice) * 100),
        status: form.status,
      });
      const url = editId ? `/api/v1/competitors/${editId}` : "/api/v1/competitors";
      const method = editId ? "PUT" : "POST";
      const res = await fetch(url, { method, headers: headers(), body });
      if (!res.ok) {
        if (res.status === 409) {
          toast.error("A competitor with this name already exists");
        } else {
          toast.error("Failed to save competitor");
        }
        return;
      }
      toast.success(editId ? "Competitor updated" : "Competitor added");
      setDialogOpen(false);
      await load();
    } catch {
      toast.error("Failed to save competitor");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this competitor?")) return;
    try {
      const res = await fetch(`/api/v1/competitors/${id}`, { method: "DELETE", headers: headers() });
      if (!res.ok) throw new Error();
      toast.success("Competitor deleted");
      await load();
    } catch {
      toast.error("Failed to delete competitor");
    }
  };

  const handleVerify = async (id: number) => {
    try {
      const res = await fetch(`/api/v1/competitors/${id}/verify`, { method: "POST", headers: headers() });
      if (!res.ok) throw new Error();
      toast.success("Marked as verified");
      await load();
    } catch {
      toast.error("Failed to verify competitor");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Competitors</h1>
          <p className="text-sm text-muted-foreground">Track competitor pricing for benchmarking. Verify regularly to keep data fresh.</p>
        </div>
        <Button onClick={openAdd}><Plus className="mr-2 h-4 w-4" />Add Competitor</Button>
      </div>

      <Card>
        <CardHeader><CardTitle>Tracked Competitors</CardTitle></CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>
          ) : competitors.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No competitors tracked yet. Add one to start benchmarking prices.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Reference Item</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Verified</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {competitors.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-1.5">
                        {c.name}
                        {c.website && (
                          <a href={c.website} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-foreground">
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </div>
                      {c.address && <p className="text-xs text-muted-foreground">{c.address}</p>}
                    </TableCell>
                    <TableCell>{c.referenceItemName || "—"}</TableCell>
                    <TableCell className="text-right">{money(c.referencePriceCents, c.currency)}</TableCell>
                    <TableCell>
                      <Badge variant={c.status === "active" ? "default" : "outline"}>{c.status}</Badge>
                    </TableCell>
                    <TableCell>
                      {c.verifiedAt ? (
                        <span className={`text-xs ${isStale(c.verifiedAt) ? "text-amber-600" : "text-muted-foreground"}`}>
                          {new Date(c.verifiedAt).toLocaleDateString()}
                          {isStale(c.verifiedAt) && " (stale)"}
                        </span>
                      ) : (
                        <span className="text-xs text-amber-600">Never</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" className="h-8 w-8" title="Mark verified" onClick={() => handleVerify(c.id)}>
                          <CheckCircle2 className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(c)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => handleDelete(c.id)}>
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

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editId ? "Edit Competitor" : "Add Competitor"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Website</Label>
              <Input value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} placeholder="https://" />
            </div>
            <div className="space-y-1.5">
              <Label>Address</Label>
              <Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Reference Item</Label>
                <Input value={form.referenceItemName} onChange={(e) => setForm({ ...form, referenceItemName: e.target.value })} placeholder="e.g. Large Pizza" />
              </div>
              <div className="space-y-1.5">
                <Label>Price</Label>
                <div className="flex gap-2">
                  <Input
                    className="w-20"
                    value={form.currency}
                    maxLength={3}
                    onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
                  />
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.referencePrice}
                    onChange={(e) => setForm({ ...form, referencePrice: e.target.value })}
                    placeholder="0.00"
                  />
                </div>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Notes</Label>
              <Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={3} />
            </div>
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v as "active" | "archived" })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="archived">Archived</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving...</> : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
