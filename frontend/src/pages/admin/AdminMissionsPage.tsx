import { useCallback, useEffect, useState } from "react";
import { Pause, Play, Plus, RefreshCw, Rocket, ShieldCheck, X } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

type Mission = {
  id: number;
  type: string;
  name: string;
  objective: string;
  hypothesis: string;
  status: string;
  holdoutPercentage: number;
  latestResult?: Record<string, unknown> | null;
};

const missionTypes = [
  "ABANDONED_CART_RECOVERY",
  "INTELLIGENT_BUNDLE",
  "LAPSED_CUSTOMER_WINBACK",
  "QUIET_HOUR_DEMAND",
  "NEW_PRODUCT_DEMAND_TEST",
];

const headers = (json = false) => ({
  Authorization: `Bearer ${localStorage.getItem("admin_token") || ""}`,
  ...(json ? { "Content-Type": "application/json" } : {}),
});

const label = (value: string) => value.replace(/_/g, " ");

export default function AdminMissionsPage() {
  const [items, setItems] = useState<Mission[]>([]);
  const [selected, setSelected] = useState<Mission | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    type: "ABANDONED_CART_RECOVERY",
    name: "",
    objective: "",
    hypothesis: "",
    holdout: "10",
    minimum: "0",
    itemAId: "",
    itemBId: "",
    bundlePrice: "",
    capacitySettingId: "",
    targetSegment: "",
    capacityLimit: "",
  });

  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/v1/missions", { headers: headers() });
      if (!response.ok) throw new Error("Mission load failed");
      setItems((await response.json()).items || []);
    } catch {
      toast.error("Could not load missions");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const detail = async (id: number) => {
    const response = await fetch(`/api/v1/missions/${id}`, { headers: headers() });
    if (response.ok) setSelected(await response.json());
    else toast.error("Could not load mission");
  };

  const missionPayload = () => {
    if (form.type === "ABANDONED_CART_RECOVERY") {
      return {
        audience: { minimumCartValueCents: Number(form.minimum || 0) },
        actions: [{ type: "SEND_EMAIL", sequence: 1, config: { noAutomaticDiscount: true } }],
      };
    }
    if (form.type === "INTELLIGENT_BUNDLE") {
      return {
        audience: {
          itemAId: Number(form.itemAId),
          itemBId: Number(form.itemBId),
          ...(form.bundlePrice ? { proposedBundlePriceCents: Number(form.bundlePrice) } : {}),
        },
        actions: [{ type: "SHOW_CART_UPSELL", sequence: 1, config: { noAutomaticDiscount: true } }],
      };
    }
    if (form.type === "QUIET_HOUR_DEMAND") {
      return {
        audience: {
          ...(form.capacitySettingId ? { capacitySettingId: Number(form.capacitySettingId) } : {}),
          ...(form.targetSegment ? { targetSegment: form.targetSegment } : {}),
        },
        capacityLimit: form.capacityLimit ? Number(form.capacityLimit) : undefined,
        actions: [{ type: "SHOW_PERSONALIZED_BANNER", sequence: 1, config: { noAutomaticDiscount: true } }],
        primaryMetric: "incremental_orders",
        guardrailMetrics: ["capacity_utilization", "stock_low", "prep_time", "cancellation_rate"],
      };
    }
    if (form.type === "NEW_PRODUCT_DEMAND_TEST") {
      return {
        audience: { conceptTest: true },
        actions: [{ type: "CREATE_LANDING_PAGE", sequence: 1, config: { noImmediateOrdering: true } }],
        primaryMetric: "qualified_interest",
        guardrailMetrics: ["preorder_refunds", "acquisition_cost", "estimated_contribution"],
      };
    }
    return {
      audience: { minimumOrderCount: 2 },
      actions: [{ type: "SEND_EMAIL", sequence: 1, config: { noAutomaticDiscount: true } }],
    };
  };

  const create = async () => {
    const payload = missionPayload();
    const response = await fetch("/api/v1/missions", {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify({
        type: form.type,
        name: form.name,
        objective: form.objective,
        hypothesis: form.hypothesis,
        holdoutPercentage: Number(form.holdout),
        ...payload,
      }),
    });
    if (!response.ok) {
      toast.error("Mission could not be created");
      return;
    }
    setOpen(false);
    toast.success("Mission created for approval");
    await load();
  };

  const act = async (action: string) => {
    if (!selected) return;
    const response = await fetch(`/api/v1/missions/${selected.id}/${action}`, {
      method: "POST",
      headers: headers(),
    });
    if (!response.ok) {
      toast.error("Mission action failed");
      return;
    }
    toast.success(`Mission ${action} request accepted`);
    await detail(selected.id);
    await load();
  };

  const bundleInvalid = form.type === "INTELLIGENT_BUNDLE" && (!form.itemAId || !form.itemBId);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold"><Rocket className="h-6 w-6" />Revenue Missions</h1>
          <p className="text-sm text-muted-foreground">Approved interventions measured against deterministic holdouts.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" />Refresh</Button>
          <Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New mission</Button>
        </div>
      </div>

      {!items.length ? (
        <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">No missions yet.</CardContent></Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {items.map((mission) => (
            <Card key={mission.id} className="cursor-pointer" onClick={() => void detail(mission.id)}>
              <CardHeader>
                <div className="flex justify-between gap-3"><CardTitle className="text-base">{mission.name}</CardTitle><Badge>{mission.status}</Badge></div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{mission.objective}</p>
                <div className="mt-3 flex flex-wrap gap-2"><Badge variant="outline">{label(mission.type)}</Badge><Badge variant="secondary">{mission.holdoutPercentage}% holdout</Badge></div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Create revenue mission</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Label>Type</Label>
            <Select value={form.type} onValueChange={(type) => setForm({ ...form, type })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{missionTypes.map((type) => <SelectItem key={type} value={type}>{label(type)}</SelectItem>)}</SelectContent>
            </Select>
            <Label>Name</Label><Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            <Label>Objective</Label><Textarea value={form.objective} onChange={(event) => setForm({ ...form, objective: event.target.value })} />
            <Label>Hypothesis</Label><Textarea value={form.hypothesis} onChange={(event) => setForm({ ...form, hypothesis: event.target.value })} />
            <Label>Holdout percentage</Label><Input type="number" min="0" max="50" value={form.holdout} onChange={(event) => setForm({ ...form, holdout: event.target.value })} />
            {form.type === "ABANDONED_CART_RECOVERY" && <><Label>Minimum cart value (cents)</Label><Input type="number" min="0" value={form.minimum} onChange={(event) => setForm({ ...form, minimum: event.target.value })} /></>}
            {form.type === "INTELLIGENT_BUNDLE" && <><Label>First menu item ID</Label><Input type="number" value={form.itemAId} onChange={(event) => setForm({ ...form, itemAId: event.target.value })} /><Label>Second menu item ID</Label><Input type="number" value={form.itemBId} onChange={(event) => setForm({ ...form, itemBId: event.target.value })} /><Label>Optional bundle display price (cents)</Label><Input type="number" value={form.bundlePrice} onChange={(event) => setForm({ ...form, bundlePrice: event.target.value })} /></>}
            {form.type === "QUIET_HOUR_DEMAND" && <><Label>Optional capacity setting ID</Label><Input type="number" value={form.capacitySettingId} onChange={(event) => setForm({ ...form, capacitySettingId: event.target.value })} /><Label>Optional target segment</Label><Input placeholder="LUNCH, LOYAL, DEAL_DEPENDENT" value={form.targetSegment} onChange={(event) => setForm({ ...form, targetSegment: event.target.value })} /><Label>Optional live capacity limit</Label><Input type="number" min="1" value={form.capacityLimit} onChange={(event) => setForm({ ...form, capacityLimit: event.target.value })} /></>}
            {form.type === "NEW_PRODUCT_DEMAND_TEST" && <p className="rounded-md bg-muted p-3 text-sm text-muted-foreground">Create the mission here, then attach concepts from Operational Missions. Public pages will always show COMING SOON, LIMITED TEST, PREORDER, or JOIN WAITLIST.</p>}
          </div>
          <DialogFooter><Button onClick={() => void create()} disabled={form.name.length < 3 || form.objective.length < 10 || form.hypothesis.length < 10 || bundleInvalid}>Create</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(selected)} onOpenChange={(value) => !value && setSelected(null)}>
        <DialogContent className="max-w-2xl">
          {selected && <>
            <DialogHeader><DialogTitle>{selected.name}</DialogTitle></DialogHeader>
            <p className="text-sm">{selected.hypothesis}</p>
            <div className="flex gap-2"><Badge>{selected.status}</Badge><Badge variant="outline">{label(selected.type)}</Badge></div>
            {selected.latestResult ? <pre className="max-h-72 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(selected.latestResult, null, 2)}</pre> : <p className="text-sm text-muted-foreground">No measured result yet.</p>}
            <DialogFooter>
              {selected.status === "NEEDS_APPROVAL" && <Button onClick={() => void act("approve")}><ShieldCheck className="mr-2 h-4 w-4" />Approve</Button>}
              {["APPROVED", "SCHEDULED", "PAUSED"].includes(selected.status) && <Button onClick={() => void act("start")}><Play className="mr-2 h-4 w-4" />Start</Button>}
              {selected.status === "RUNNING" && <Button variant="outline" onClick={() => void act("pause")}><Pause className="mr-2 h-4 w-4" />Pause</Button>}
              <Button variant="secondary" onClick={() => void act("evaluate")}>Evaluate</Button>
              {!["COMPLETED", "CANCELLED"].includes(selected.status) && <Button variant="destructive" onClick={() => void act("cancel")}><X className="mr-2 h-4 w-4" />Cancel</Button>}
            </DialogFooter>
          </>}
        </DialogContent>
      </Dialog>
    </div>
  );
}
