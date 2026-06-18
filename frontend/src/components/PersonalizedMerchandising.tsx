import { useEffect, useMemo, useState } from "react";
import { Gift, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getSessionId, getVisitorId, track } from "@/lib/analytics";

type Merchandising = {
  offers: Array<{ id: number; code: string; title: string; description: string }>;
  items: Array<{ id: number; name: string; priceCents: number }>;
};

export function PersonalizedMerchandising() {
  const [data, setData] = useState<Merchandising | null>(null);
  const visitorId = useMemo(() => getVisitorId(), []);
  const sessionId = useMemo(() => getSessionId(), []);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/personalized-merchandising", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visitorId, sessionId, placement: "HOME" }),
      signal: controller.signal,
    })
      .then((response) => response.ok ? response.json() : null)
      .then((result) => setData(result && (result.offers?.length || result.items?.length) ? result : null))
      .catch(() => undefined);
    return () => controller.abort();
  }, [sessionId, visitorId]);

  if (!data) return null;
  const offer = data.offers[0];

  return (
    <section className="mx-auto max-w-6xl px-4 py-6">
      <Card>
        <CardContent className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge variant="outline" className="mb-2">{offer ? <Gift className="mr-2 h-3 w-3" /> : <Sparkles className="mr-2 h-3 w-3" />}Personalized picks</Badge>
            <h2 className="text-xl font-semibold">{offer?.title || "Recommended for today"}</h2>
            <p className="text-sm text-muted-foreground">{offer?.description || data.items.map((item) => item.name).slice(0, 3).join(", ")}</p>
            {offer && <p className="mt-2 text-xs text-muted-foreground">Private code: <span className="font-semibold">{offer.code}</span></p>}
          </div>
          <Button asChild onClick={() => track("personalized_merchandising_clicked", { properties: { offerId: offer?.id } })}>
            <Link to="/menu">Explore picks</Link>
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
