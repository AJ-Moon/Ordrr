import { useEffect, useMemo, useState } from "react";
import { Bell, ClipboardList, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getSessionId, getVisitorId, track } from "@/lib/analytics";

type Concept = {
  id: number;
  missionId?: number | null;
  name: string;
  description: string;
  category: string;
  presentationMode: string;
  presentationLabel: string;
  ctaLabel: string;
  availabilityNotice: string;
  variants: Array<{ id: number; name: string; description: string; priceCents?: number | null; servingClaim?: string | null }>;
};

export default function ProductConceptsPage() {
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [emails, setEmails] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const visitorId = useMemo(() => getVisitorId(), []);
  const sessionId = useMemo(() => getSessionId(), []);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 7000);
    fetch("/api/v1/product-concepts/public", { signal: controller.signal })
      .then((response) => response.ok ? response.json() : { items: [] })
      .then((data) => setConcepts(data.items || []))
      .catch(() => setConcepts([]))
      .finally(() => {
        window.clearTimeout(timeout);
        setLoading(false);
      });
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  const register = async (concept: Concept) => {
    const variant = concept.variants[0];
    const preorder = concept.presentationMode === "PREORDER";
    const response = await fetch(`/api/v1/product-concepts/${concept.id}/${preorder ? "preorder" : "waitlist"}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        visitorId,
        sessionId,
        variantId: variant?.id,
        email: emails[concept.id] || undefined,
        quantity: 1,
        priceCents: preorder ? variant?.priceCents : undefined,
        properties: { page: "concepts" },
      }),
    });
    if (!response.ok) {
      toast.error("We could not save that request");
      return;
    }
    track("product_concept_interest", {
      missionId: concept.missionId ? String(concept.missionId) : undefined,
      variantId: variant ? String(variant.id) : undefined,
      properties: { conceptId: concept.id, presentationMode: concept.presentationMode },
    });
    toast.success(preorder ? "Preorder interest reserved" : "You are on the list");
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="mx-auto max-w-6xl px-4 py-12">
        <div className="mb-8 max-w-3xl">
          <Badge variant="outline" className="mb-3"><Sparkles className="mr-2 h-3 w-3" />Product Lab</Badge>
          <h1 className="text-4xl font-bold tracking-tight">Coming soon and limited-test ideas</h1>
          <p className="mt-3 text-muted-foreground">These concepts help us test demand before launch. They are not available for immediate menu ordering.</p>
        </div>

        {loading ? (
          <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">Loading concepts...</CardContent></Card>
        ) : concepts.length === 0 ? (
          <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">No product concepts are open right now.</CardContent></Card>
        ) : (
          <div className="grid gap-5 md:grid-cols-2">
            {concepts.map((concept) => {
              const variant = concept.variants[0];
              return (
                <Card key={concept.id} className="overflow-hidden">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <Badge>{concept.presentationLabel}</Badge>
                        <CardTitle className="mt-3">{concept.name}</CardTitle>
                      </div>
                      <Badge variant="outline">{concept.category}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">{concept.description}</p>
                    {variant && (
                      <div className="rounded-lg border bg-muted/30 p-3">
                        <p className="font-medium">{variant.name}</p>
                        <p className="text-sm text-muted-foreground">{variant.description}</p>
                        {variant.priceCents != null && <p className="mt-1 text-sm font-semibold">Test price: ${(variant.priceCents / 100).toFixed(2)}</p>}
                      </div>
                    )}
                    <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">{concept.availabilityNotice}</p>
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <Input
                        type="email"
                        placeholder="Email for updates"
                        value={emails[concept.id] || ""}
                        onChange={(event) => setEmails({ ...emails, [concept.id]: event.target.value })}
                      />
                      <Button onClick={() => void register(concept)}>
                        {concept.presentationMode === "PREORDER" ? <ClipboardList className="mr-2 h-4 w-4" /> : <Bell className="mr-2 h-4 w-4" />}
                        {concept.ctaLabel}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
