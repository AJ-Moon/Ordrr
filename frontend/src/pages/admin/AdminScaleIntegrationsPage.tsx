import { useCallback, useEffect, useState } from "react";
import { PlugZap, RefreshCw, Shield, SlidersHorizontal } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type Integration = { id: number; provider: string; integrationType: string; channel?: string | null; status: string; lastError?: string | null };

const headers = (json = false) => ({
  Authorization: `Bearer ${localStorage.getItem("admin_token") || ""}`,
  ...(json ? { "Content-Type": "application/json" } : {}),
});

export default function AdminScaleIntegrationsPage() {
  const [benchmark, setBenchmark] = useState<unknown>(null);
  const [review, setReview] = useState<unknown>(null);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [form, setForm] = useState({ provider: "sendgrid", integrationType: "MESSAGING", channel: "email", status: "DISABLED", secretReference: "" });

  const load = useCallback(async () => {
    const [benchmarkResponse, reviewResponse, integrationResponse] = await Promise.all([
      fetch("/api/v1/neighborhood-benchmarks/latest", { headers: headers() }),
      fetch("/api/v1/admin/performance-review/latest", { headers: headers() }),
      fetch("/api/v1/admin/integrations", { headers: headers() }),
    ]);
    if (benchmarkResponse.ok) setBenchmark((await benchmarkResponse.json()).snapshot);
    if (reviewResponse.ok) setReview((await reviewResponse.json()).review);
    if (integrationResponse.ok) setIntegrations((await integrationResponse.json()).items || []);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const queue = async (path: string, label: string) => {
    const response = await fetch(path, { method: "POST", headers: headers() });
    toast[response.ok ? "success" : "error"](response.ok ? `${label} queued` : `${label} failed`);
  };

  const saveIntegration = async () => {
    const response = await fetch("/api/v1/admin/integrations", {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify({ ...form, secretReference: form.secretReference || null, settings: {} }),
    });
    if (!response.ok) {
      toast.error("Integration could not be saved");
      return;
    }
    toast.success("Integration saved");
    await load();
  };

  const testIntegration = async (id: number) => {
    const response = await fetch(`/api/v1/admin/integrations/${id}/test`, { method: "POST", headers: headers() });
    const data = await response.json().catch(() => ({}));
    toast[response.ok && data.ok ? "success" : "error"](data.ok ? "Integration check passed" : data.error || "Integration check failed");
    await load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div><h1 className="text-2xl font-bold">Scale & Integrations</h1><p className="text-sm text-muted-foreground">Privacy benchmarks, provider scaffolding, queue health, and performance reviews.</p></div>
        <Button variant="outline" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" />Refresh</Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between"><CardTitle className="flex items-center gap-2"><Shield className="h-5 w-5" />Neighborhood Benchmarks</CardTitle><Button size="sm" onClick={() => void queue("/api/v1/neighborhood-benchmarks/refresh", "Benchmark refresh")}>Queue</Button></CardHeader>
          <CardContent>{benchmark ? <pre className="max-h-80 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(benchmark, null, 2)}</pre> : <p className="text-sm text-muted-foreground">No benchmark snapshot yet.</p>}</CardContent>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between"><CardTitle className="flex items-center gap-2"><SlidersHorizontal className="h-5 w-5" />Performance Review</CardTitle><Button size="sm" onClick={() => void queue("/api/v1/admin/performance-review/refresh", "Performance review")}>Queue</Button></CardHeader>
          <CardContent>{review ? <pre className="max-h-80 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(review, null, 2)}</pre> : <p className="text-sm text-muted-foreground">No performance review yet.</p>}</CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><PlugZap className="h-5 w-5" />Provider Integrations</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-5">
            <div><Label>Provider</Label><Input value={form.provider} onChange={(event) => setForm({ ...form, provider: event.target.value })} /></div>
            <div><Label>Type</Label><Select value={form.integrationType} onValueChange={(integrationType) => setForm({ ...form, integrationType })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="MESSAGING">Messaging</SelectItem><SelectItem value="ADVERTISING">Advertising</SelectItem></SelectContent></Select></div>
            <div><Label>Channel</Label><Input value={form.channel} onChange={(event) => setForm({ ...form, channel: event.target.value })} /></div>
            <div><Label>Status</Label><Select value={form.status} onValueChange={(status) => setForm({ ...form, status })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="DISABLED">Disabled</SelectItem><SelectItem value="CONFIGURED">Configured</SelectItem></SelectContent></Select></div>
            <div><Label>Secret ref</Label><Input value={form.secretReference} onChange={(event) => setForm({ ...form, secretReference: event.target.value })} /></div>
          </div>
          <Button onClick={() => void saveIntegration()}>Save integration</Button>
          <div className="grid gap-3 md:grid-cols-2">
            {integrations.map((item) => <Card key={item.id}><CardContent className="flex items-center justify-between gap-3 p-4"><div><p className="font-semibold">{item.provider} {item.channel || ""}</p><p className="text-xs text-muted-foreground">{item.integrationType} {item.lastError ? `· ${item.lastError}` : ""}</p></div><div className="flex items-center gap-2"><Badge>{item.status}</Badge><Button size="sm" variant="outline" onClick={() => void testIntegration(item.id)}>Test</Button></div></CardContent></Card>)}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
