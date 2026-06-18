import { useState, useEffect } from "react";
import { Navigate, Link } from "react-router-dom";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Star, ShoppingBag, Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

interface RewardSettings {
  minRedeem: number;
  conversionRate: number;
  pointsPerDollar: number;
  rewardsEnabled: boolean;
}

interface OrderActivity {
  id: string;
  createdAt: string;
  pointsEarned: number;
  total: number;
}

interface PointsTx {
  type: "earn" | "redeem" | "expire";
  points: number;
  balanceAfter: number;
  orderId: string | null;
  createdAt: string;
}

export default function PointsPage() {
  const { user, token } = useAuth();
  const [currentPoints, setCurrentPoints] = useState(0);
  const [settings, setSettings] = useState<RewardSettings | null>(null);
  const [activity, setActivity] = useState<OrderActivity[]>([]);
  const [txHistory, setTxHistory] = useState<PointsTx[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!token) return;

    const fetchAll = async () => {
      try {
        const [pointsRes, settingsRes, historyRes, txRes] = await Promise.all([
          fetch("/api/rewards/points", {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch("/api/rewards/settings"),
          fetch("/api/orders/history", {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch("/api/rewards/history", {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);
        if (pointsRes.ok) {
          const d = await pointsRes.json();
          setCurrentPoints(d.points ?? 0);
        }
        if (settingsRes.ok) {
          setSettings(await settingsRes.json());
        }
        if (historyRes.ok) {
          const orders: OrderActivity[] = await historyRes.json();
          setActivity(orders.filter((o) => o.pointsEarned > 0).slice(0, 6));
        }
        if (txRes.ok) {
          setTxHistory(await txRes.json());
        }
      } catch {
        // ignore
      } finally {
        setIsLoading(false);
      }
    };

    fetchAll();
  }, [token]);

  if (!user)
    return <Navigate to="/login" state={{ from: "/points" }} replace />;

  const minRedeem = settings?.minRedeem ?? 100;
  const progress = Math.min((currentPoints / minRedeem) * 100, 100);
  const canRedeem = currentPoints >= minRedeem;
  const pointsValue = settings
    ? (currentPoints * settings.conversionRate).toFixed(2)
    : null;

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return iso;
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="py-8 md:py-12">
        <div className="mx-auto max-w-4xl px-4 lg:px-8">
          <div className="mb-8 text-center">
            <h1 className="font-serif text-3xl font-bold md:text-4xl text-foreground mb-2">
              Your Points
            </h1>
            <p className="text-muted-foreground">
              Earn points with every order and redeem them at checkout.
            </p>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {/* Balance + Next Threshold */}
              <div className="grid gap-6 md:grid-cols-3 mb-8">
                <Card className="md:col-span-2 bg-linear-to-br from-primary/10 to-primary/5 border-primary/20">
                  <CardContent className="p-8 flex items-center justify-between">
                    <div>
                      <p className="mb-1 text-sm font-medium text-muted-foreground">
                        Current Balance
                      </p>
                      <div className="flex items-baseline gap-2">
                        <span className="font-serif text-4xl font-bold text-primary sm:text-5xl">
                          {currentPoints}
                        </span>
                        <span className="text-base font-medium text-primary sm:text-lg">
                          pts
                        </span>
                      </div>
                      {pointsValue && (
                        <p className="mt-1 text-sm text-muted-foreground">
                          ≈ ${pointsValue} value
                        </p>
                      )}
                    </div>
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-secondary/20 sm:h-20 sm:w-20">
                      <Star className="h-8 w-8 fill-secondary text-secondary sm:h-10 sm:w-10" />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">Redeem Threshold</CardTitle>
                    <CardDescription>
                      {canRedeem
                        ? "You can redeem at checkout!"
                        : `${minRedeem - currentPoints} pts until you can redeem`}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Progress value={progress} className="h-2 mb-3" />
                    <p className="text-sm font-medium text-foreground">
                      {currentPoints} / {minRedeem} pts minimum
                    </p>
                  </CardContent>
                </Card>
              </div>

              {/* Earn rate info */}
              {settings && (
                <Card className="mb-8">
                  <CardContent className="p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                      <p className="font-medium text-foreground">How to earn</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        Earn{" "}
                        <span className="font-semibold text-primary">
                          {settings.pointsPerDollar} point
                          {settings.pointsPerDollar !== 1 ? "s" : ""}
                        </span>{" "}
                        for every $1 spent on orders. Points are applied
                        automatically — no code needed.
                      </p>
                    </div>
                    <Button asChild variant="outline" className="shrink-0">
                      <Link to="/menu">Order Now</Link>
                    </Button>
                  </CardContent>
                </Card>
              )}

              {/* How to redeem */}
              <Card className="mb-8 border-primary/20">
                <CardContent className="p-6">
                  <p className="font-medium text-foreground mb-1">
                    How to redeem
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Your points are automatically offered at checkout once you
                    reach {minRedeem} pts. You can redeem up to 50% of any order
                    total.
                    {settings &&
                      ` Each point is worth $${settings.conversionRate.toFixed(3)}.`}
                  </p>
                </CardContent>
              </Card>

              {/* Points History */}
              <h2 className="font-serif text-2xl font-semibold mb-4 mt-10 text-foreground">
                Points History
              </h2>
              {txHistory.length === 0 ? (
                <Card className="mb-8">
                  <CardContent className="py-8 text-center">
                    <p className="text-sm text-muted-foreground">
                      No history yet.
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <Card className="mb-8">
                  <CardContent className="p-0">
                    <div className="divide-y divide-border">
                      {txHistory.map((tx, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between px-4 py-3 text-sm"
                        >
                          <div className="flex items-center gap-3">
                            <span
                              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                                tx.type === "earn"
                                  ? "bg-green-100 text-green-700"
                                  : tx.type === "redeem"
                                    ? "bg-amber-100 text-amber-700"
                                    : "bg-red-100 text-red-700"
                              }`}
                            >
                              {tx.type}
                            </span>
                            <span className="text-muted-foreground">
                              {formatDate(tx.createdAt)}
                            </span>
                            {tx.orderId && (
                              <span className="font-mono text-xs text-muted-foreground">
                                #{tx.orderId}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-4">
                            <span
                              className={`font-semibold ${
                                tx.points > 0
                                  ? "text-green-600"
                                  : "text-red-500"
                              }`}
                            >
                              {tx.points > 0 ? "+" : ""}
                              {tx.points} pts
                            </span>
                            <span className="text-xs text-muted-foreground w-20 text-right">
                              bal: {tx.balanceAfter}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Recent Activity */}
              <h2 className="font-serif text-2xl font-semibold mb-4 text-foreground">
                Recent Activity
              </h2>
              {activity.length === 0 ? (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                      <ShoppingBag className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <p className="font-medium text-foreground mb-1">
                      No points earned yet
                    </p>
                    <p className="text-sm text-muted-foreground mb-4">
                      Place your first order to start earning!
                    </p>
                    <Button asChild variant="outline">
                      <Link to="/menu">Browse Menu</Link>
                    </Button>
                  </CardContent>
                </Card>
              ) : (
                <Card>
                  <CardContent className="p-0">
                    <div className="divide-y divide-border">
                      {activity.map((item) => (
                        <div
                          key={item.id}
                          className="flex justify-between items-center p-4"
                        >
                          <div>
                            <p className="font-medium text-foreground">
                              Order #{item.id}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {formatDate(item.createdAt)} · $
                              {item.total.toFixed(2)}
                            </p>
                          </div>
                          <span className="font-semibold text-green-600">
                            +{item.pointsEarned} pts
                          </span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
