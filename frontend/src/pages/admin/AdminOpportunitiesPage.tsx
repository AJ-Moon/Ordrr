import { useCallback, useEffect, useState } from "react";
import { Check, Eye, FlaskConical, Lightbulb, Loader2, MessageSquare, Play, RefreshCw, Rocket, X } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

type Opportunity = {
  id: number;
  type: string;
  headline: string;
  summary: string;
  status: string;
  trend: string;
  priorityScore: number;
  impactScore: number;
  confidenceScore: number;
  estimatedRevenueImpactCents: number | null;
  periodStart: string;
  periodEnd: string;
  evidence: Record<string, unknown>;
  recommendedAction: { description?: string };
  aiExplanation?: {
    business_problem?: string;
    evidence_summary?: string;
    interpretation?: string;
    recommended_action?: string;
    risks?: string[];
    required_human_checks?: string[];
  } | null;
  comments?: Array<{ id: number; actorId: string; body: string; createdAt: string }>;
};

const headers = (json = false) => ({
  Authorization: `Bearer ${localStorage.getItem("admin_token") || ""}`,
  ...(json ? { "Content-Type": "application/json" } : {}),
});

const scoreColor = (score: number) => score >= 75 ? "text-red-600" : score >= 50 ? "text-amber-600" : "text-emerald-600";

export default function AdminOpportunitiesPage() {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [status, setStatus] = useState("active");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState("");
  const [selected, setSelected] = useState<Opportunity | null>(null);
  const [dismissReason, setDismissReason] = useState("");
  const [comment, setComment] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const query = status === "active" ? "" : `?status=${status}`;
      const response = await fetch(`/api/v1/opportunities${query}`, { headers: headers() });
      if (!response.ok) throw new Error();
      setItems((await response.json()).items || []);
    } catch {
      toast.error("Could not load opportunities");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => { void load(); }, [load]);

  const openDetail = async (id: number) => {
    try {
      const response = await fetch(`/api/v1/opportunities/${id}`, { headers: headers() });
      if (!response.ok) throw new Error();
      setSelected(await response.json());
    } catch {
      toast.error("Could not load opportunity details");
    }
  };

  const queueJob = async (job: string) => {
    setRunning(job);
    try {
      const response = await fetch(`/api/v1/admin/jobs/${job}/run`, { method: "POST", headers: headers() });
      if (!response.ok) throw new Error();
      toast.success(`${job} queued. The worker will process it.`);
    } catch {
      toast.error("Could not queue opportunity processing");
    } finally {
      setRunning("");
    }
  };

  const transition = async (action: "approve" | "dismiss") => {
    if (!selected) return;
    if (action === "dismiss" && dismissReason.trim().length < 3) {
      toast.error("Add a dismissal reason");
      return;
    }
    const response = await fetch(`/api/v1/opportunities/${selected.id}/${action}`, {
      method: "POST",
      headers: headers(action === "dismiss"),
      body: action === "dismiss" ? JSON.stringify({ reason: dismissReason.trim() }) : undefined,
    });
    if (!response.ok) {
      toast.error("Opportunity status could not be changed");
      return;
    }
    toast.success(action === "approve" ? "Opportunity approved" : "Opportunity dismissed");
    setSelected(null);
    setDismissReason("");
    await load();
  };

  const addComment = async () => {
    if (!selected || !comment.trim()) return;
    const response = await fetch(`/api/v1/opportunities/${selected.id}/comments`, {
      method: "POST", headers: headers(true), body: JSON.stringify({ body: comment.trim() }),
    });
    if (!response.ok) {
      toast.error("Comment could not be added");
      return;
    }
    setComment("");
    await openDetail(selected.id);
  };

  const convert = async (target: "experiment" | "mission") => {
    if (!selected) return;
    const missionType = selected.type === "BUNDLE_OPPORTUNITY" ? "INTELLIGENT_BUNDLE" : selected.type === "LAPSED_CUSTOMER_POOL" ? "LAPSED_CUSTOMER_WINBACK" : "ABANDONED_CART_RECOVERY";
    const body = target === "experiment"
      ? { experimentType: selected.type === "BUNDLE_OPPORTUNITY" ? "UPSELL" : "BUTTON_COPY", placement: selected.type === "BUNDLE_OPPORTUNITY" ? "CART_UPSELL" : "HOME_PROMO_COPY" }
      : { missionType, holdoutPercentage: 10 };
    const response = await fetch(`/api/v1/opportunities/${selected.id}/create-${target}`, { method: "POST", headers: headers(true), body: JSON.stringify(body) });
    if (!response.ok) { toast.error(`Could not create ${target}`); return; }
    toast.success(`${target === "experiment" ? "Experiment" : "Mission"} created for approval`);
    setSelected(null); await load();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold"><Lightbulb className="h-6 w-6" />Opportunities</h1>
          <p className="text-sm text-muted-foreground">Deterministic findings ranked by impact, confidence, effort and urgency.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="active">All statuses</SelectItem>
              {['RECOMMENDED','APPROVED','DISMISSED','EXPIRED'].map((value) => <SelectItem value={value} key={value}>{value}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</Button>
          <Button variant="outline" onClick={() => void queueJob("opportunities.detect_daily")} disabled={Boolean(running)}><Play className="mr-2 h-4 w-4" />Detect</Button>
          <Button onClick={() => void queueJob("opportunities.generate_weekly_cards")} disabled={Boolean(running)}>{running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Lightbulb className="mr-2 h-4 w-4" />}Generate Cards</Button>
        </div>
      </div>

      {items.length === 0 ? (
        <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">{loading ? "Loading opportunities…" : "No opportunities match this view. Run analytics aggregation before detection."}</CardContent></Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {items.map((item) => (
            <Card key={item.id} className="cursor-pointer transition-shadow hover:shadow-md" onClick={() => void openDetail(item.id)}>
              <CardHeader className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <CardTitle className="text-base">{item.headline}</CardTitle>
                  <span className={`text-2xl font-bold ${scoreColor(item.priorityScore)}`}>{item.priorityScore.toFixed(0)}</span>
                </div>
                <div className="flex flex-wrap gap-2"><Badge>{item.status}</Badge><Badge variant="outline">{item.type.replace(/_/g, " ")}</Badge><Badge variant="secondary">{item.trend}</Badge></div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">{item.summary}</p>
                <div className="grid grid-cols-3 gap-2 text-center text-xs"><div className="rounded border p-2">Impact<br /><strong>{item.impactScore.toFixed(0)}</strong></div><div className="rounded border p-2">Confidence<br /><strong>{item.confidenceScore.toFixed(0)}</strong></div><div className="rounded border p-2">Priority<br /><strong>{item.priorityScore.toFixed(0)}</strong></div></div>
                <div className="flex items-center justify-between text-xs text-muted-foreground"><span>{item.periodStart} to {item.periodEnd}</span><span className="flex items-center gap-1"><Eye className="h-3 w-3" />Review</span></div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={Boolean(selected)} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          {selected && <>
            <DialogHeader><DialogTitle>{selected.headline}</DialogTitle><DialogDescription>{selected.type.replace(/_/g, " ")} · Priority {selected.priorityScore.toFixed(0)} · {selected.status}</DialogDescription></DialogHeader>
            <div className="space-y-4">
              <p className="text-sm">{selected.summary}</p>
              <section><h3 className="mb-2 font-semibold">Verified Evidence</h3><pre className="max-h-64 overflow-auto rounded bg-muted p-3 text-xs whitespace-pre-wrap">{JSON.stringify(selected.evidence, null, 2)}</pre></section>
              <section><h3 className="mb-2 font-semibold">Recommended Action</h3><p className="text-sm text-muted-foreground">{selected.recommendedAction?.description || "Human review required."}</p></section>
              {selected.aiExplanation && <section className="rounded-lg border p-4"><h3 className="mb-2 font-semibold">AI Explanation</h3><p className="text-sm">{selected.aiExplanation.interpretation || selected.aiExplanation.business_problem}</p><p className="mt-2 text-sm text-muted-foreground">{selected.aiExplanation.recommended_action}</p></section>}
              <section className="space-y-2"><h3 className="font-semibold">Review Notes</h3>{selected.comments?.map((entry) => <div className="rounded border p-2 text-sm" key={entry.id}><p>{entry.body}</p><p className="mt-1 text-xs text-muted-foreground">{new Date(entry.createdAt).toLocaleString()}</p></div>)}<div className="flex gap-2"><Input value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add a review note" maxLength={2000} /><Button variant="outline" onClick={() => void addComment()}><MessageSquare className="h-4 w-4" /></Button></div></section>
              {['DETECTED','NEEDS_REVIEW','RECOMMENDED'].includes(selected.status) && <Textarea value={dismissReason} onChange={(event) => setDismissReason(event.target.value)} placeholder="Dismissal reason (required only when dismissing)" maxLength={1000} />}
            </div>
            <DialogFooter>
              {['DETECTED','NEEDS_REVIEW','RECOMMENDED'].includes(selected.status) && <><Button variant="destructive" onClick={() => void transition("dismiss")}><X className="mr-2 h-4 w-4" />Dismiss</Button><Button onClick={() => void transition("approve")}><Check className="mr-2 h-4 w-4" />Approve</Button></>}
              {selected.status === "APPROVED" && <><Button variant="outline" onClick={() => void convert("experiment")}><FlaskConical className="mr-2 h-4 w-4" />Create Experiment</Button><Button onClick={() => void convert("mission")}><Rocket className="mr-2 h-4 w-4" />Create Mission</Button></>}
            </DialogFooter>
          </>}
        </DialogContent>
      </Dialog>
    </div>
  );
}
