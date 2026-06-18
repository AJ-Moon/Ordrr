import { useCallback, useEffect, useState } from "react";
import { Brain, Gift, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

type Offer = { id: number; code: string; title: string; description: string; discountType: string; discountValue: number; status: string };
type DemandTwin = { metrics?: Record<string, unknown>; segments?: Record<string, unknown>; menuInsights?: unknown[]; generatedAt?: string };

const headers = (json = false) => ({
  Authorization: `Bearer ${localStorage.getItem("admin_token") || ""}`,
  ...(json ? { "Content-Type": "application/json" } : {}),
});

export default function AdminAdvancedConversionPage() {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [twin, setTwin] = useState<DemandTwin | null>(null);
  const [form, setForm] = useState({ code: "", title: "", description: "", discountType: "PERCENT", discountValue: "10", minimumSubtotalCents: "0", minimumMarginCents: "0" });

  const load = useCallback(async () => {
    const [offersResponse, twinResponse] = await Promise.all([
      fetch("/api/v1/private-offers", { headers: headers() }),
      fetch("/api/v1/tenant-demand-twin/latest", { headers: headers() }),
    ]);
    if (offersResponse.ok) setOffers((await offersResponse.json()).items || []);
    if (twinResponse.ok) setTwin((await twinResponse.json()).snapshot || null);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const createOffer = async () => {
    const response = await fetch("/api/v1/private-offers", {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify({
        code: form.code,
        title: form.title,
        description: form.description,
        discountType: form.discountType,
        discountValue: Number(form.discountValue),
        minimumSubtotalCents: Number(form.minimumSubtotalCents),
        minimumMarginCents: Number(form.minimumMarginCents),
      }),
    });
    if (!response.ok) {
      toast.error("Offer could not be created");
      return;
    }
    toast.success("Private offer created");
    await load();
  };

  const action = async (offer: Offer, next: string) => {
    const response = await fetch(`/api/v1/private-offers/${offer.id}/${next}`, { method: "POST", headers: headers() });
    if (!response.ok) {
      toast.error("Offer action failed");
      return;
    }
    await load();
  };

  const refreshTwin = async () => {
    const response = await fetch("/api/v1/tenant-demand-twin/refresh", { method: "POST", headers: headers() });
    toast[response.ok ? "success" : "error"](response.ok ? "Demand Twin refresh queued" : "Could not queue refresh");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div><h1 className="text-2xl font-bold">Advanced Conversion</h1><p className="text-sm text-muted-foreground">Private offers, personalized merchandising, and first-party Demand Twin.</p></div>
        <Button variant="outline" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" />Refresh</Button>
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Gift className="h-5 w-5" />Private Offers</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <div><Label>Code</Label><Input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })} /></div>
            <div><Label>Title</Label><Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></div>
            <div><Label>Discount type</Label><Select value={form.discountType} onValueChange={(discountType) => setForm({ ...form, discountType })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="PERCENT">Percent</SelectItem><SelectItem value="FIXED">Fixed cents</SelectItem></SelectContent></Select></div>
            <div><Label>Discount value</Label><Input type="number" value={form.discountValue} onChange={(event) => setForm({ ...form, discountValue: event.target.value })} /></div>
            <div><Label>Minimum subtotal cents</Label><Input type="number" value={form.minimumSubtotalCents} onChange={(event) => setForm({ ...form, minimumSubtotalCents: event.target.value })} /></div>
            <div><Label>Minimum margin cents</Label><Input type="number" value={form.minimumMarginCents} onChange={(event) => setForm({ ...form, minimumMarginCents: event.target.value })} /></div>
            <div className="md:col-span-3"><Label>Description</Label><Textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
          </div>
          <Button onClick={() => void createOffer()} disabled={form.code.length < 3 || form.title.length < 3 || form.description.length < 10}><Plus className="mr-2 h-4 w-4" />Create offer</Button>
          <div className="grid gap-3 md:grid-cols-2">
            {offers.map((offer) => <Card key={offer.id}><CardContent className="space-y-3 p-4"><div className="flex justify-between gap-3"><div><p className="font-semibold">{offer.title}</p><p className="text-xs text-muted-foreground">{offer.code} · {offer.discountType} {offer.discountValue}</p></div><Badge>{offer.status}</Badge></div><p className="text-sm text-muted-foreground">{offer.description}</p><div className="flex gap-2">{offer.status === "DRAFT" && <Button size="sm" onClick={() => void action(offer, "approve")}>Approve</Button>}{["APPROVED", "PAUSED"].includes(offer.status) && <Button size="sm" onClick={() => void action(offer, "start")}>Start</Button>}{offer.status === "RUNNING" && <Button size="sm" variant="outline" onClick={() => void action(offer, "pause")}>Pause</Button>}</div></CardContent></Card>)}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between"><CardTitle className="flex items-center gap-2"><Brain className="h-5 w-5" />Tenant Demand Twin</CardTitle><Button size="sm" onClick={() => void refreshTwin()}>Queue Refresh</Button></CardHeader>
        <CardContent>{twin ? <pre className="max-h-96 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(twin, null, 2)}</pre> : <p className="text-sm text-muted-foreground">No Demand Twin snapshot yet.</p>}</CardContent>
      </Card>
    </div>
  );
}
