import { useEffect, useMemo, useState } from "react";
import { Clock3, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getSessionId, getVisitorId, track } from "@/lib/analytics";

type QuietHourOffer = {
  missionId: number;
  offer: {
    headline: string;
    body: string;
    items: Array<{ id: number; name: string; priceCents: number; image?: string | null }>;
  };
};

export function QuietHourBanner() {
  const [offer, setOffer] = useState<QuietHourOffer | null>(null);
  const visitorId = useMemo(() => getVisitorId(), []);
  const sessionId = useMemo(() => getSessionId(), []);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/mission-assignments/quiet-hour", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visitorId, sessionId }),
      signal: controller.signal,
    })
      .then((response) => response.ok ? response.json() : null)
      .then((result) => setOffer(result?.assigned ? result : null))
      .catch(() => undefined);
    return () => controller.abort();
  }, [sessionId, visitorId]);

  if (!offer) return null;

  return (
    <section className="mx-auto max-w-6xl px-4 py-6">
      <Card className="border-primary/30 bg-primary/5">
        <CardContent className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge variant="outline" className="mb-2"><Clock3 className="mr-2 h-3 w-3" />Quiet-hour offer</Badge>
            <h2 className="text-xl font-semibold">{offer.offer.headline}</h2>
            <p className="text-sm text-muted-foreground">{offer.offer.body}</p>
            <p className="mt-2 text-xs text-muted-foreground">
              Featured now: {offer.offer.items.map((item) => item.name).slice(0, 3).join(", ")}
            </p>
          </div>
          <Button asChild onClick={() => track("promotion_clicked", { missionId: String(offer.missionId), properties: { type: "quiet_hour" } })}>
            <Link to="/menu"><Sparkles className="mr-2 h-4 w-4" />View menu</Link>
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
