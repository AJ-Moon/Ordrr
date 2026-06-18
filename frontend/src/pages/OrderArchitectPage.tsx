import { useMemo, useState } from "react";
import { ChefHat, Loader2, Plus, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCart } from "@/contexts/CartContext";
import { getSessionId, getVisitorId, track } from "@/lib/analytics";

type SuggestionItem = {
  menuItemId: number;
  name: string;
  category: string;
  quantity: number;
  priceCents: number;
  lineTotalCents: number;
};

type Suggestion = {
  status: string;
  items: SuggestionItem[];
  subtotalCents: number;
  estimatedMarginCents?: number | null;
  explanation?: string;
};

export default function OrderArchitectPage() {
  const { addItem } = useCart();
  const visitorId = useMemo(() => getVisitorId(), []);
  const sessionId = useMemo(() => getSessionId(), []);
  const [budget, setBudget] = useState("25");
  const [partySize, setPartySize] = useState("2");
  const [dietary, setDietary] = useState("");
  const [excluded, setExcluded] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);

  const suggest = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/v1/order-architect/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          visitorId,
          sessionId,
          budgetCents: Math.round(Number(budget || 0) * 100),
          partySize: Number(partySize || 1),
          dietaryConstraints: dietary.split(",").map((item) => item.trim()).filter(Boolean),
          excludedIngredients: excluded.split(",").map((item) => item.trim()).filter(Boolean),
          preferences: {},
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not build an order");
      setSuggestion(data);
      track("order_architect_suggested", { properties: { status: data.status, subtotalCents: data.subtotalCents } });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not build an order");
    } finally {
      setLoading(false);
    }
  };

  const addSuggestion = () => {
    if (!suggestion?.items.length) return;
    for (const item of suggestion.items) {
      addItem({ menuItemId: item.menuItemId, name: item.name, price: item.priceCents / 100, image: "" }, item.quantity);
    }
    toast.success("Suggested order added to cart");
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="mx-auto max-w-5xl px-4 py-12">
        <div className="mb-8 max-w-3xl">
          <Badge variant="outline" className="mb-3"><ChefHat className="mr-2 h-3 w-3" />Order Architect</Badge>
          <h1 className="text-4xl font-bold tracking-tight">Build a cart around your budget</h1>
          <p className="mt-3 text-muted-foreground">Server-validated recommendations using live menu availability and prices.</p>
        </div>

        <Card>
          <CardContent className="grid gap-4 p-5 md:grid-cols-4">
            <div><Label>Budget</Label><Input type="number" min="0" value={budget} onChange={(event) => setBudget(event.target.value)} /></div>
            <div><Label>Party size</Label><Input type="number" min="1" max="30" value={partySize} onChange={(event) => setPartySize(event.target.value)} /></div>
            <div><Label>Dietary constraints</Label><Input placeholder="vegetarian, not_spicy" value={dietary} onChange={(event) => setDietary(event.target.value)} /></div>
            <div><Label>Exclude</Label><Input placeholder="mushroom, beef" value={excluded} onChange={(event) => setExcluded(event.target.value)} /></div>
            <div className="md:col-span-4"><Button onClick={() => void suggest()} disabled={loading}>{loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}Build my order</Button></div>
          </CardContent>
        </Card>

        {suggestion && (
          <Card className="mt-6">
            <CardHeader><CardTitle>{suggestion.status === "COMPLETED" ? "Suggested cart" : "No matching cart yet"}</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">{suggestion.explanation}</p>
              {suggestion.items.map((item) => (
                <div key={item.menuItemId} className="flex items-center justify-between rounded-lg border p-3">
                  <div><p className="font-medium">{item.name}</p><p className="text-xs text-muted-foreground">{item.category}</p></div>
                  <p className="font-semibold">${(item.lineTotalCents / 100).toFixed(2)}</p>
                </div>
              ))}
              {suggestion.items.length > 0 && <div className="flex items-center justify-between"><p className="font-semibold">Subtotal ${(suggestion.subtotalCents / 100).toFixed(2)}</p><Button onClick={addSuggestion}><Plus className="mr-2 h-4 w-4" />Add to cart</Button></div>}
            </CardContent>
          </Card>
        )}
      </main>
      <Footer />
    </div>
  );
}
