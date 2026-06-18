import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function headers() {
  return { Authorization: `Bearer ${localStorage.getItem("admin_token") || ""}` };
}

function money(cents: number | null | undefined) {
  return cents == null ? "—" : `$${(cents / 100).toFixed(2)}`;
}

function pct(value: number | null | undefined) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function defaultRange() {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - 29);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { from: fmt(from), to: fmt(to) };
}

type Overview = {
  sessions: number;
  menuSessions: number;
  cartSessions: number;
  checkoutSessions: number;
  orderingSessions: number;
  completedOrders: number;
  revenueCents: number;
  contributionMarginCents: number | null;
  conversionRate: number | null;
};

type ItemRow = {
  itemId: number;
  name: string;
  category: string | null;
  isAvailable: boolean;
  impressions: number;
  detailViews: number;
  addToCarts: number;
  orders: number;
  quantitySold: number;
  revenueCents: number;
  contributionMarginCents: number | null;
  uniqueDetailViewSessions: number;
  detailViewRate: number | null;
  addToCartRate: number | null;
  purchaseRate: number | null;
  cartSurvivalRate: number | null;
  classification: "HERO" | "LEAKING" | "HIDDEN_WINNER" | "WEAK" | "INSUFFICIENT_DATA";
  classificationConfidence: number;
  minimumSampleWarning: boolean;
};

type FunnelDay = {
  date: string;
  sessions: number;
  menuSessions: number;
  cartSessions: number;
  checkoutSessions: number;
  orderingSessions: number;
  completedOrders: number;
  revenueCents: number;
};

type SearchRow = {
  query: string;
  searches: number;
  zeroResultSearches: number;
  clicks: number;
  addToCarts: number;
  orders: number;
};

type CheckoutRow = {
  step: string;
  entered: number;
  completed: number;
  failures: number;
  dropOffRate: number | null;
};

type SourceRow = {
  source: string;
  medium: string;
  campaign: string | null;
  sessions: number;
  orders: number;
  revenueCents: number;
  contributionMarginCents: number | null;
  conversionRate: number | null;
};

type ChatRow = {
  intent: string;
  messages: number;
  recommendations: number;
  clicks: number;
};

type BasketPair = {
  itemAId: number;
  itemAName: string;
  itemBId: number;
  itemBName: string;
  pairOrders: number;
  support: number | null;
  confidence: number | null;
  lift: number | null;
};

type CustomerRow = {
  segment: string;
  customers: number;
  orders: number;
  revenueCents: number;
};

const TABS = [
  { value: "overview", label: "Overview" },
  { value: "items", label: "Menu Matrix" },
  { value: "funnel", label: "Funnel" },
  { value: "search", label: "Search" },
  { value: "checkout", label: "Checkout" },
  { value: "sources", label: "Sources" },
  { value: "chat", label: "Chat" },
  { value: "baskets", label: "Baskets" },
  { value: "customers", label: "Customers" },
] as const;

type TabValue = (typeof TABS)[number]["value"];

export default function AdminAnalyticsPage() {
  const [range, setRange] = useState(defaultRange());
  const [tab, setTab] = useState<TabValue>("overview");
  const [loading, setLoading] = useState(false);
  const [loadedTabs, setLoadedTabs] = useState<Set<TabValue>>(new Set());

  const [overview, setOverview] = useState<Overview | null>(null);
  const [items, setItems] = useState<ItemRow[]>([]);
  const [funnel, setFunnel] = useState<FunnelDay[]>([]);
  const [search, setSearch] = useState<SearchRow[]>([]);
  const [checkout, setCheckout] = useState<CheckoutRow[]>([]);
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [chat, setChat] = useState<ChatRow[]>([]);
  const [baskets, setBaskets] = useState<{ start: string | null; end: string | null; pairs: BasketPair[] }>({
    start: null,
    end: null,
    pairs: [],
  });
  const [customers, setCustomers] = useState<CustomerRow[]>([]);

  const qs = `from=${range.from}&to=${range.to}`;

  const loadTab = useCallback(
    async (target: TabValue) => {
      setLoading(true);
      try {
        switch (target) {
          case "overview": {
            const res = await fetch(`/api/v1/analytics/overview?${qs}`, { headers: headers() });
            if (!res.ok) throw new Error();
            setOverview(await res.json());
            break;
          }
          case "items": {
            const res = await fetch(`/api/v1/analytics/items?${qs}`, { headers: headers() });
            if (!res.ok) throw new Error();
            setItems((await res.json()).items || []);
            break;
          }
          case "funnel": {
            const res = await fetch(`/api/v1/analytics/funnel?${qs}`, { headers: headers() });
            if (!res.ok) throw new Error();
            setFunnel((await res.json()).days || []);
            break;
          }
          case "search": {
            const res = await fetch(`/api/v1/analytics/search?${qs}`, { headers: headers() });
            if (!res.ok) throw new Error();
            setSearch((await res.json()).queries || []);
            break;
          }
          case "checkout": {
            const res = await fetch(`/api/v1/analytics/checkout?${qs}`, { headers: headers() });
            if (!res.ok) throw new Error();
            setCheckout((await res.json()).steps || []);
            break;
          }
          case "sources": {
            const res = await fetch(`/api/v1/analytics/sources?${qs}`, { headers: headers() });
            if (!res.ok) throw new Error();
            setSources((await res.json()).sources || []);
            break;
          }
          case "chat": {
            const res = await fetch(`/api/v1/analytics/chat?${qs}`, { headers: headers() });
            if (!res.ok) throw new Error();
            setChat((await res.json()).intents || []);
            break;
          }
          case "baskets": {
            const res = await fetch(`/api/v1/analytics/baskets`, { headers: headers() });
            if (!res.ok) throw new Error();
            const data = await res.json();
            setBaskets({ start: data.window?.start ?? null, end: data.window?.end ?? null, pairs: data.pairs || [] });
            break;
          }
          case "customers": {
            const res = await fetch(`/api/v1/analytics/customers?${qs}`, { headers: headers() });
            if (!res.ok) throw new Error();
            setCustomers((await res.json()).segments || []);
            break;
          }
        }
      } catch {
        toast.error("Could not load analytics data");
      } finally {
        setLoading(false);
      }
    },
    [qs],
  );

  // Load the active tab whenever the date range changes (invalidate cache)
  useEffect(() => {
    setLoadedTabs(new Set());
  }, [range.from, range.to]);

  useEffect(() => {
    if (loadedTabs.has(tab)) return;
    void loadTab(tab).then(() => setLoadedTabs((prev) => new Set(prev).add(tab)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, loadedTabs, qs]);

  const refresh = () => {
    setLoadedTabs(new Set());
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-sm text-muted-foreground">Funnel, menu, search, checkout, source, chat and customer performance.</p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            type="date"
            value={range.from}
            onChange={(e) => setRange((r) => ({ ...r, from: e.target.value }))}
            className="h-9 w-36 text-sm"
          />
          <span className="text-sm text-muted-foreground">to</span>
          <Input
            type="date"
            value={range.to}
            onChange={(e) => setRange((r) => ({ ...r, to: e.target.value }))}
            className="h-9 w-36 text-sm"
          />
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as TabValue)}>
        <TabsList className="flex-wrap h-auto">
          {TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab data={overview} loading={loading} />
        </TabsContent>
        <TabsContent value="items">
          <ItemsTab rows={items} loading={loading} />
        </TabsContent>
        <TabsContent value="funnel">
          <FunnelTab rows={funnel} loading={loading} />
        </TabsContent>
        <TabsContent value="search">
          <SearchTab rows={search} loading={loading} />
        </TabsContent>
        <TabsContent value="checkout">
          <CheckoutTab rows={checkout} loading={loading} />
        </TabsContent>
        <TabsContent value="sources">
          <SourcesTab rows={sources} loading={loading} />
        </TabsContent>
        <TabsContent value="chat">
          <ChatTab rows={chat} loading={loading} />
        </TabsContent>
        <TabsContent value="baskets">
          <BasketsTab data={baskets} loading={loading} />
        </TabsContent>
        <TabsContent value="customers">
          <CustomersTab rows={customers} loading={loading} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return <p className="py-8 text-center text-sm text-muted-foreground">{message}</p>;
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function OverviewTab({ data, loading }: { data: Overview | null; loading: boolean }) {
  if (!data) return <EmptyState message={loading ? "Loading…" : "No data available."} />;
  if (data.sessions === 0) {
    return <EmptyState message="No sessions recorded for this date range yet." />;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label="Sessions" value={data.sessions.toLocaleString()} />
      <StatCard label="Menu Sessions" value={data.menuSessions.toLocaleString()} />
      <StatCard label="Cart Sessions" value={data.cartSessions.toLocaleString()} />
      <StatCard label="Checkout Sessions" value={data.checkoutSessions.toLocaleString()} />
      <StatCard label="Ordering Sessions" value={data.orderingSessions.toLocaleString()} />
      <StatCard label="Completed Orders" value={data.completedOrders.toLocaleString()} />
      <StatCard label="Revenue" value={money(data.revenueCents)} />
      <StatCard label="Contribution Margin" value={money(data.contributionMarginCents)} />
      <StatCard label="Conversion Rate" value={pct(data.conversionRate)} />
    </div>
  );
}

function ItemsTab({ rows, loading }: { rows: ItemRow[]; loading: boolean }) {
  if (rows.length === 0) return <EmptyState message={loading ? "Loading…" : "No menu items found."} />;
  const counts = rows.reduce<Record<string, number>>((result, row) => {
    result[row.classification] = (result[row.classification] || 0) + 1;
    return result;
  }, {});
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {(["HERO", "LEAKING", "HIDDEN_WINNER", "WEAK", "INSUFFICIENT_DATA"] as const).map((classification) => (
          <StatCard key={classification} label={classification.replace(/_/g, " ")} value={String(counts[classification] || 0)} />
        ))}
      </div>
      <Card>
        <CardHeader><CardTitle>Item Funnel &amp; Menu Matrix</CardTitle></CardHeader>
        <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead>Category</TableHead>
              <TableHead className="text-right">Impressions</TableHead>
              <TableHead className="text-right">Detail Views</TableHead>
              <TableHead className="text-right">View Rate</TableHead>
              <TableHead className="text-right">Add to Cart</TableHead>
              <TableHead className="text-right">Cart Rate</TableHead>
              <TableHead className="text-right">Orders</TableHead>
              <TableHead className="text-right">Purchase Rate</TableHead>
              <TableHead>Matrix</TableHead>
              <TableHead className="text-right">Revenue</TableHead>
              <TableHead className="text-right">Margin</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.itemId}>
                <TableCell className="font-medium">
                  {row.name}
                  {!row.isAvailable && <Badge variant="outline" className="ml-2">Unavailable</Badge>}
                </TableCell>
                <TableCell>{row.category || "—"}</TableCell>
                <TableCell className="text-right">{row.impressions.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.detailViews.toLocaleString()}</TableCell>
                <TableCell className="text-right">{pct(row.detailViewRate)}</TableCell>
                <TableCell className="text-right">{row.addToCarts.toLocaleString()}</TableCell>
                <TableCell className="text-right">{pct(row.addToCartRate)}</TableCell>
                <TableCell className="text-right">{row.orders.toLocaleString()}</TableCell>
                <TableCell className="text-right">{pct(row.purchaseRate)}</TableCell>
                <TableCell><Badge variant={row.classification === "LEAKING" ? "destructive" : "outline"}>{row.classification.replace(/_/g, " ")}</Badge>{row.minimumSampleWarning && <span className="ml-2 text-xs text-amber-600">Low sample</span>}</TableCell>
                <TableCell className="text-right">{money(row.revenueCents)}</TableCell>
                <TableCell className="text-right">{money(row.contributionMarginCents)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function FunnelTab({ rows, loading }: { rows: FunnelDay[]; loading: boolean }) {
  if (rows.length === 0) return <EmptyState message={loading ? "Loading…" : "No funnel data for this date range yet."} />;
  return (
    <Card>
      <CardHeader><CardTitle>Daily Funnel</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead className="text-right">Sessions</TableHead>
              <TableHead className="text-right">Menu</TableHead>
              <TableHead className="text-right">Cart</TableHead>
              <TableHead className="text-right">Checkout</TableHead>
              <TableHead className="text-right">Ordering</TableHead>
              <TableHead className="text-right">Completed</TableHead>
              <TableHead className="text-right">Revenue</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.date}>
                <TableCell className="font-medium">{row.date}</TableCell>
                <TableCell className="text-right">{row.sessions.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.menuSessions.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.cartSessions.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.checkoutSessions.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.orderingSessions.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.completedOrders.toLocaleString()}</TableCell>
                <TableCell className="text-right">{money(row.revenueCents)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function SearchTab({ rows, loading }: { rows: SearchRow[]; loading: boolean }) {
  if (rows.length === 0) return <EmptyState message={loading ? "Loading…" : "No searches recorded for this date range yet."} />;
  return (
    <Card>
      <CardHeader><CardTitle>Search Gaps</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Query</TableHead>
              <TableHead className="text-right">Searches</TableHead>
              <TableHead className="text-right">Zero Results</TableHead>
              <TableHead className="text-right">Clicks</TableHead>
              <TableHead className="text-right">Add to Cart</TableHead>
              <TableHead className="text-right">Orders</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.query}>
                <TableCell className="font-medium">{row.query || "(empty)"}</TableCell>
                <TableCell className="text-right">{row.searches.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.zeroResultSearches.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.clicks.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.addToCarts.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.orders.toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function CheckoutTab({ rows, loading }: { rows: CheckoutRow[]; loading: boolean }) {
  if (rows.length === 0) return <EmptyState message={loading ? "Loading…" : "No checkout activity for this date range yet."} />;
  return (
    <Card>
      <CardHeader><CardTitle>Checkout Friction</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Step</TableHead>
              <TableHead className="text-right">Entered</TableHead>
              <TableHead className="text-right">Completed</TableHead>
              <TableHead className="text-right">Failures</TableHead>
              <TableHead className="text-right">Drop-off Rate</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.step}>
                <TableCell className="font-medium">{row.step}</TableCell>
                <TableCell className="text-right">{row.entered.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.completed.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.failures.toLocaleString()}</TableCell>
                <TableCell className="text-right">{pct(row.dropOffRate)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function SourcesTab({ rows, loading }: { rows: SourceRow[]; loading: boolean }) {
  if (rows.length === 0) return <EmptyState message={loading ? "Loading…" : "No acquisition data for this date range yet."} />;
  return (
    <Card>
      <CardHeader><CardTitle>Acquisition &amp; Campaign Conversion</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Source</TableHead>
              <TableHead>Medium</TableHead>
              <TableHead>Campaign</TableHead>
              <TableHead className="text-right">Sessions</TableHead>
              <TableHead className="text-right">Orders</TableHead>
              <TableHead className="text-right">Revenue</TableHead>
              <TableHead className="text-right">Margin</TableHead>
              <TableHead className="text-right">Conversion</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, i) => (
              <TableRow key={`${row.source}-${row.medium}-${row.campaign}-${i}`}>
                <TableCell className="font-medium">{row.source}</TableCell>
                <TableCell>{row.medium}</TableCell>
                <TableCell>{row.campaign || "—"}</TableCell>
                <TableCell className="text-right">{row.sessions.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.orders.toLocaleString()}</TableCell>
                <TableCell className="text-right">{money(row.revenueCents)}</TableCell>
                <TableCell className="text-right">{money(row.contributionMarginCents)}</TableCell>
                <TableCell className="text-right">{pct(row.conversionRate)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function ChatTab({ rows, loading }: { rows: ChatRow[]; loading: boolean }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        message={
          loading
            ? "Loading…"
            : "No chat activity recorded for this date range yet. Chat tracking starts capturing data as customers use the chat widget."
        }
      />
    );
  }
  return (
    <Card>
      <CardHeader><CardTitle>Chat Intents</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Intent</TableHead>
              <TableHead className="text-right">Messages</TableHead>
              <TableHead className="text-right">Recommendations</TableHead>
              <TableHead className="text-right">Clicks</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.intent}>
                <TableCell className="font-medium">{row.intent}</TableCell>
                <TableCell className="text-right">{row.messages.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.recommendations.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.clicks.toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function BasketsTab({
  data,
  loading,
}: {
  data: { start: string | null; end: string | null; pairs: BasketPair[] };
  loading: boolean;
}) {
  if (data.pairs.length === 0) {
    return (
      <EmptyState
        message={loading ? "Loading…" : "No basket associations computed yet. Run the basket-association job once enough orders exist."}
      />
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Basket Associations
          {data.start && data.end && (
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              Window: {data.start} to {data.end}
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item A</TableHead>
              <TableHead>Item B</TableHead>
              <TableHead className="text-right">Orders Together</TableHead>
              <TableHead className="text-right">Support</TableHead>
              <TableHead className="text-right">Confidence</TableHead>
              <TableHead className="text-right">Lift</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.pairs.map((pair) => (
              <TableRow key={`${pair.itemAId}-${pair.itemBId}`}>
                <TableCell className="font-medium">{pair.itemAName}</TableCell>
                <TableCell className="font-medium">{pair.itemBName}</TableCell>
                <TableCell className="text-right">{pair.pairOrders.toLocaleString()}</TableCell>
                <TableCell className="text-right">{pair.support != null ? pair.support.toFixed(3) : "—"}</TableCell>
                <TableCell className="text-right">{pair.confidence != null ? pair.confidence.toFixed(3) : "—"}</TableCell>
                <TableCell className="text-right">{pair.lift != null ? pair.lift.toFixed(2) : "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function CustomersTab({ rows, loading }: { rows: CustomerRow[]; loading: boolean }) {
  if (rows.length === 0) return <EmptyState message={loading ? "Loading…" : "No customer data for this date range yet."} />;
  return (
    <Card>
      <CardHeader><CardTitle>Customer Segments</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Segment</TableHead>
              <TableHead className="text-right">Customers</TableHead>
              <TableHead className="text-right">Orders</TableHead>
              <TableHead className="text-right">Revenue</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.segment}>
                <TableCell className="font-medium capitalize">{row.segment}</TableCell>
                <TableCell className="text-right">{row.customers.toLocaleString()}</TableCell>
                <TableCell className="text-right">{row.orders.toLocaleString()}</TableCell>
                <TableCell className="text-right">{money(row.revenueCents)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
