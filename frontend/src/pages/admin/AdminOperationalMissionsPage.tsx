import { useCallback, useEffect, useState } from "react";
import { Boxes, ClipboardList, Gauge, Plus, RefreshCw, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

type CapacitySetting = {
  id: number;
  locationId: number;
  weekday: number;
  timeStart: string;
  timeEnd: string;
  normalCapacityOrders: number;
  maximumCapacityOrders: number;
  targetUtilization: number;
  enabled: boolean;
};

type InventoryItem = {
  itemId: number;
  name: string;
  availableQuantity?: number | null;
  lowStockThreshold: number;
  constrained: boolean;
};

type ProductConcept = {
  id: number;
  missionId?: number | null;
  name: string;
  status: string;
  presentationLabel: string;
  ctaLabel: string;
  variants: Array<{ id: number; name: string; priceCents?: number | null }>;
};

const headers = (json = false) => ({
  Authorization: `Bearer ${localStorage.getItem("admin_token") || ""}`,
  ...(json ? { "Content-Type": "application/json" } : {}),
});

export default function AdminOperationalMissionsPage() {
  const [capacity, setCapacity] = useState<CapacitySetting[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [concepts, setConcepts] = useState<ProductConcept[]>([]);
  const [loading, setLoading] = useState(false);
  const [capacityForm, setCapacityForm] = useState({
    locationId: "",
    weekday: "1",
    timeStart: "14:00",
    timeEnd: "17:00",
    normalCapacityOrders: "10",
    maximumCapacityOrders: "18",
    targetUtilization: "0.75",
  });
  const [conceptForm, setConceptForm] = useState({
    missionId: "",
    name: "",
    description: "",
    category: "",
    estimatedCostCents: "0",
    estimatedPreparationTimeMinutes: "15",
    targetSegment: "",
    presentationMode: "JOIN_WAITLIST",
    variantName: "",
    variantDescription: "",
    priceCents: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [capacityResponse, inventoryResponse, conceptResponse] = await Promise.all([
        fetch("/api/v1/capacity-settings", { headers: headers() }),
        fetch("/api/v1/inventory-guardrails", { headers: headers() }),
        fetch("/api/v1/product-concepts", { headers: headers() }),
      ]);
      if (capacityResponse.ok) setCapacity((await capacityResponse.json()).items || []);
      if (inventoryResponse.ok) setInventory((await inventoryResponse.json()).items || []);
      if (conceptResponse.ok) setConcepts((await conceptResponse.json()).items || []);
      if (!capacityResponse.ok && !inventoryResponse.ok && !conceptResponse.ok) throw new Error("Phase 6 unavailable");
    } catch {
      toast.error("Could not load operational mission controls");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const createCapacity = async () => {
    const response = await fetch("/api/v1/capacity-settings", {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify({
        locationId: Number(capacityForm.locationId),
        weekday: Number(capacityForm.weekday),
        timeStart: capacityForm.timeStart,
        timeEnd: capacityForm.timeEnd,
        normalCapacityOrders: Number(capacityForm.normalCapacityOrders),
        maximumCapacityOrders: Number(capacityForm.maximumCapacityOrders),
        targetUtilization: Number(capacityForm.targetUtilization),
        enabled: true,
      }),
    });
    if (!response.ok) {
      toast.error("Capacity setting was not saved");
      return;
    }
    toast.success("Capacity setting saved");
    await load();
  };

  const toggleInventory = async (item: InventoryItem) => {
    const response = await fetch(`/api/v1/inventory-guardrails/${item.itemId}`, {
      method: "PUT",
      headers: headers(true),
      body: JSON.stringify({
        availableQuantity: item.availableQuantity ?? null,
        lowStockThreshold: item.lowStockThreshold || 0,
        constrained: !item.constrained,
        notes: !item.constrained ? "Constrained from operational missions" : "",
      }),
    });
    if (!response.ok) {
      toast.error("Inventory guardrail was not updated");
      return;
    }
    toast.success("Inventory guardrail updated");
    await load();
  };

  const createConcept = async () => {
    const response = await fetch("/api/v1/product-concepts", {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify({
        missionId: conceptForm.missionId ? Number(conceptForm.missionId) : null,
        name: conceptForm.name,
        description: conceptForm.description,
        category: conceptForm.category,
        estimatedCostCents: Number(conceptForm.estimatedCostCents),
        estimatedPreparationTimeMinutes: Number(conceptForm.estimatedPreparationTimeMinutes),
        targetSegment: conceptForm.targetSegment || null,
        presentationMode: conceptForm.presentationMode,
        variants: [{
          variantKey: "primary",
          name: conceptForm.variantName || conceptForm.name,
          description: conceptForm.variantDescription || conceptForm.description,
          priceCents: conceptForm.priceCents ? Number(conceptForm.priceCents) : null,
          isControl: true,
        }],
      }),
    });
    if (!response.ok) {
      toast.error("Concept was not created");
      return;
    }
    toast.success("Product concept created");
    await load();
  };

  const conceptAction = async (id: number, action: string) => {
    const response = await fetch(`/api/v1/product-concepts/${id}/${action}`, {
      method: "POST",
      headers: headers(),
    });
    if (!response.ok) {
      toast.error("Concept action failed");
      return;
    }
    toast.success(`Concept ${action} accepted`);
    await load();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Operational Missions</h1>
          <p className="text-sm text-muted-foreground">Quiet-hour capacity, inventory guardrails, and new-product demand tests.</p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</Button>
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Gauge className="h-5 w-5" />Capacity Settings</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            <div><Label>Location ID</Label><Input value={capacityForm.locationId} onChange={(event) => setCapacityForm({ ...capacityForm, locationId: event.target.value })} /></div>
            <div><Label>Weekday (0 Sunday)</Label><Input type="number" min="0" max="6" value={capacityForm.weekday} onChange={(event) => setCapacityForm({ ...capacityForm, weekday: event.target.value })} /></div>
            <div><Label>Start</Label><Input type="time" value={capacityForm.timeStart} onChange={(event) => setCapacityForm({ ...capacityForm, timeStart: event.target.value })} /></div>
            <div><Label>End</Label><Input type="time" value={capacityForm.timeEnd} onChange={(event) => setCapacityForm({ ...capacityForm, timeEnd: event.target.value })} /></div>
            <div><Label>Normal orders</Label><Input type="number" min="1" value={capacityForm.normalCapacityOrders} onChange={(event) => setCapacityForm({ ...capacityForm, normalCapacityOrders: event.target.value })} /></div>
            <div><Label>Maximum orders</Label><Input type="number" min="1" value={capacityForm.maximumCapacityOrders} onChange={(event) => setCapacityForm({ ...capacityForm, maximumCapacityOrders: event.target.value })} /></div>
            <div><Label>Target utilization</Label><Input type="number" step="0.01" min="0.01" max="1" value={capacityForm.targetUtilization} onChange={(event) => setCapacityForm({ ...capacityForm, targetUtilization: event.target.value })} /></div>
            <div className="flex items-end"><Button onClick={() => void createCapacity()} disabled={!capacityForm.locationId}><Plus className="mr-2 h-4 w-4" />Save window</Button></div>
          </div>
          <Table>
            <TableHeader><TableRow><TableHead>ID</TableHead><TableHead>Location</TableHead><TableHead>Window</TableHead><TableHead>Capacity</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
            <TableBody>{capacity.map((row) => <TableRow key={row.id}><TableCell>{row.id}</TableCell><TableCell>{row.locationId}</TableCell><TableCell>Day {row.weekday}, {row.timeStart}-{row.timeEnd}</TableCell><TableCell>{row.normalCapacityOrders}/{row.maximumCapacityOrders} at {(row.targetUtilization * 100).toFixed(0)}%</TableCell><TableCell><Badge variant={row.enabled ? "default" : "outline"}>{row.enabled ? "enabled" : "disabled"}</Badge></TableCell></TableRow>)}</TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><ShieldAlert className="h-5 w-5" />Inventory Guardrails</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Item</TableHead><TableHead>Stock</TableHead><TableHead>Threshold</TableHead><TableHead>Guardrail</TableHead><TableHead /></TableRow></TableHeader>
            <TableBody>{inventory.slice(0, 30).map((item) => <TableRow key={item.itemId}><TableCell>{item.name}</TableCell><TableCell>{item.availableQuantity ?? "not tracked"}</TableCell><TableCell>{item.lowStockThreshold}</TableCell><TableCell><Badge variant={item.constrained ? "destructive" : "outline"}>{item.constrained ? "constrained" : "eligible"}</Badge></TableCell><TableCell><Button size="sm" variant="outline" onClick={() => void toggleInventory(item)}>{item.constrained ? "Clear" : "Constrain"}</Button></TableCell></TableRow>)}</TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Boxes className="h-5 w-5" />Product Concepts</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <div><Label>Demand mission ID (optional)</Label><Input value={conceptForm.missionId} onChange={(event) => setConceptForm({ ...conceptForm, missionId: event.target.value })} /></div>
            <div><Label>Presentation</Label><Select value={conceptForm.presentationMode} onValueChange={(presentationMode) => setConceptForm({ ...conceptForm, presentationMode })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["COMING_SOON", "LIMITED_TEST", "PREORDER", "JOIN_WAITLIST"].map((mode) => <SelectItem key={mode} value={mode}>{mode.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Name</Label><Input value={conceptForm.name} onChange={(event) => setConceptForm({ ...conceptForm, name: event.target.value })} /></div>
            <div><Label>Category</Label><Input value={conceptForm.category} onChange={(event) => setConceptForm({ ...conceptForm, category: event.target.value })} /></div>
            <div><Label>Estimated cost (cents)</Label><Input type="number" min="0" value={conceptForm.estimatedCostCents} onChange={(event) => setConceptForm({ ...conceptForm, estimatedCostCents: event.target.value })} /></div>
            <div><Label>Prep minutes</Label><Input type="number" min="1" value={conceptForm.estimatedPreparationTimeMinutes} onChange={(event) => setConceptForm({ ...conceptForm, estimatedPreparationTimeMinutes: event.target.value })} /></div>
            <div><Label>Variant name</Label><Input value={conceptForm.variantName} onChange={(event) => setConceptForm({ ...conceptForm, variantName: event.target.value })} /></div>
            <div><Label>Variant price (cents)</Label><Input type="number" min="0" value={conceptForm.priceCents} onChange={(event) => setConceptForm({ ...conceptForm, priceCents: event.target.value })} /></div>
            <div className="md:col-span-2"><Label>Description</Label><Textarea value={conceptForm.description} onChange={(event) => setConceptForm({ ...conceptForm, description: event.target.value })} /></div>
            <div className="md:col-span-2"><Label>Variant description</Label><Textarea value={conceptForm.variantDescription} onChange={(event) => setConceptForm({ ...conceptForm, variantDescription: event.target.value })} /></div>
          </div>
          <Button onClick={() => void createConcept()} disabled={conceptForm.name.length < 3 || conceptForm.description.length < 20}><ClipboardList className="mr-2 h-4 w-4" />Create concept</Button>
          <div className="grid gap-3 md:grid-cols-2">
            {concepts.map((concept) => <Card key={concept.id}><CardContent className="space-y-3 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{concept.name}</p><p className="text-xs text-muted-foreground">Mission {concept.missionId || "not linked"}</p></div><Badge>{concept.status}</Badge></div><div className="flex flex-wrap gap-2"><Badge variant="outline">{concept.presentationLabel}</Badge><Badge variant="secondary">{concept.ctaLabel}</Badge></div><div className="flex flex-wrap gap-2">{concept.status === "DRAFT" && <Button size="sm" onClick={() => void conceptAction(concept.id, "approve")}>Approve</Button>}{["APPROVED", "PAUSED"].includes(concept.status) && <Button size="sm" onClick={() => void conceptAction(concept.id, "start")}>Start public page</Button>}{concept.status === "RUNNING" && <Button size="sm" variant="outline" onClick={() => void conceptAction(concept.id, "pause")}>Pause</Button>}</div></CardContent></Card>)}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
