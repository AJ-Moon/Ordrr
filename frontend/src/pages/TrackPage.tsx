import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search, CheckCircle2, ChefHat, Package, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRestaurant } from "@/contexts/RestaurantContext";

const statusSteps = [
  { label: "Received", icon: CheckCircle2, key: "received" },
  { label: "Preparing", icon: ChefHat, key: "preparing" },
  { label: "Ready", icon: Package, key: "ready" },
  { label: "Delivered", icon: Package, key: "delivered" },
];

const topSteps = [
  { label: "Received", key: "received" },
  { label: "Preparing", key: "preparing" },
  { label: "Ready", key: "ready" },
  { label: "Delivered", key: "delivered" },
];

function normalizeTrackStatus(
  status: string,
): "received" | "preparing" | "ready" | "delivered" {
  if (status === "delivered") return "delivered";
  if (status === "ready" || status === "out_for_delivery") return "ready";
  if (status === "preparing") return "preparing";
  return "received";
}

type OrderItem = { name: string; quantity: number; price: number };
type Order = {
  id: string;
  status: string;
  address: string;
  createdAt: string;
  items: OrderItem[];
  total: number;
  orderType: string;
};

export default function TrackPage() {
  const [searchParams] = useSearchParams();
  const initialOrderId = searchParams.get("order_id") || "";
  const initialPhone = searchParams.get("phone") || "";

  const [orderNumber, setOrderNumber] = useState(initialOrderId);
  const [phone, setPhone] = useState(initialPhone);
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");
  const [isTracking, setIsTracking] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { primaryColor } = useRestaurant();

  const TERMINAL_STATUSES = ["delivered", "cancelled"];

  const pollOrder = async (id: string, ph: string) => {
    try {
      const params = new URLSearchParams({ order_id: id, phone: ph });
      const res = await fetch(`/api/orders/track?${params}`);
      if (!res.ok) return;
      const data: Order = await res.json();
      setOrder(data);
      setLastUpdated(new Date());
      if (TERMINAL_STATUSES.includes(data.status)) {
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    } catch {
      // silently ignore poll failures
    }
  };

  // Start/stop polling whenever isTracking changes
  useEffect(() => {
    if (!isTracking || !order) return;
    if (TERMINAL_STATUSES.includes(order.status)) return;

    intervalRef.current = setInterval(() => {
      pollOrder(orderNumber, phone);
    }, 20_000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isTracking]);

  const doFetchOrder = async (id: string, ph: string) => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setError("");
    setOrder(null);
    setIsTracking(false);
    setLastUpdated(null);
    if (!id.trim() || !ph.trim()) {
      setError("Please enter your order number and phone number.");
      return;
    }
    try {
      const params = new URLSearchParams({
        order_id: id.trim(),
        phone: ph.trim(),
      });
      const res = await fetch(`/api/orders/track?${params}`);
      if (!res.ok) {
        setError(
          res.status === 404
            ? "Order not found. Check your order number and phone."
            : "Could not fetch order.",
        );
        return;
      }
      const data: Order = await res.json();
      setOrder(data);
      setLastUpdated(new Date());
      setIsTracking(true);
    } catch {
      setError("Network error. Please try again.");
    }
  };

  useEffect(() => {
    if (initialOrderId && initialPhone) {
      doFetchOrder(initialOrderId, initialPhone);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTrack = async (e: React.FormEvent) => {
    e.preventDefault();
    doFetchOrder(orderNumber, phone);
  };

  const normalizedStatus = order ? normalizeTrackStatus(order.status) : null;

  const currentStepIndex = normalizedStatus
    ? statusSteps.findIndex((s) => s.key === normalizedStatus)
    : -1;

  const topStepIndex = normalizedStatus
    ? topSteps.findIndex((s) => s.key === normalizedStatus)
    : -1;

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="pb-20 md:pb-0">
        {/* Page Header */}
        <section className="bg-muted/40 border-b border-border py-10 lg:py-14">
          <div className="mx-auto max-w-7xl px-4 text-center lg:px-8">
            <h1 className="font-serif text-3xl font-extrabold text-foreground md:text-4xl">
              Track Your Order
            </h1>
            <p className="mt-2 text-muted-foreground">
              Enter your order number and phone to see real-time updates
            </p>
          </div>
        </section>

        <div className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
          {/* Top horizontal stepper — always visible */}
          <div className="mx-auto mb-10 max-w-2xl">
            <div className="flex items-center justify-between">
              {topSteps.map((step, idx) => {
                const isComplete = order ? topStepIndex >= idx : false;
                const isCurrent = order ? topStepIndex === idx : false;
                return (
                  <div key={step.key} className="flex flex-1 items-center">
                    <div className="flex flex-col items-center gap-1.5">
                      <div
                        className={cn(
                          "flex h-9 w-9 items-center justify-center rounded-full border-2 text-xs font-bold transition-all",
                          isComplete
                            ? "border-transparent text-white"
                            : isCurrent
                              ? "border-current text-white"
                              : "border-border bg-background text-muted-foreground",
                        )}
                        style={
                          isComplete || isCurrent
                            ? {
                                backgroundColor: primaryColor,
                                borderColor: primaryColor,
                              }
                            : {}
                        }
                      >
                        {isComplete && !isCurrent ? (
                          <CheckCircle2 className="h-4 w-4" />
                        ) : (
                          <span>{idx + 1}</span>
                        )}
                      </div>
                      <span
                        className={cn(
                          "hidden text-xs font-medium sm:block",
                          isComplete || isCurrent
                            ? "text-foreground"
                            : "text-muted-foreground",
                        )}
                      >
                        {step.label}
                      </span>
                    </div>
                    {/* Connector line */}
                    {idx < topSteps.length - 1 && (
                      <div
                        className={cn(
                          "mx-2 h-0.5 flex-1 rounded-full transition-all",
                          isComplete ? "" : "bg-border",
                        )}
                        style={
                          isComplete ? { backgroundColor: primaryColor } : {}
                        }
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Search form in a card */}
          <Card className="mx-auto mb-10 max-w-md shadow-lg">
            <CardHeader className="pb-4">
              <CardTitle className="font-serif text-xl">
                Find your order
              </CardTitle>
              <CardDescription>
                Enter the details from your confirmation
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleTrack} className="space-y-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <Input
                    type="text"
                    placeholder="Order number (e.g., FH-12345)"
                    value={orderNumber}
                    onChange={(e) => setOrderNumber(e.target.value)}
                    className="pl-10 h-12"
                  />
                </div>
                <Input
                  type="tel"
                  placeholder="Phone number used when ordering"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="h-12"
                />
                <Button
                  type="submit"
                  size="lg"
                  className="w-full h-12"
                  style={{ backgroundColor: primaryColor }}
                >
                  Track Order
                </Button>
              </form>
              {error && (
                <p className="mt-3 text-center text-sm text-destructive">
                  {error}
                </p>
              )}
            </CardContent>
          </Card>

          {isTracking && order && (
            <div className="grid lg:grid-cols-3 gap-8 max-w-6xl mx-auto">
              {/* Order Status */}
              <div className="lg:col-span-2 space-y-6">
                <Card>
                  <CardHeader className="pb-4">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                      <div>
                        <CardTitle className="font-serif text-xl">
                          Order #{order.id}
                        </CardTitle>
                        <CardDescription>
                          Placed on {new Date(order.createdAt).toLocaleString()}
                        </CardDescription>
                      </div>
                      <div className="flex flex-col items-start sm:items-end gap-1.5">
                        <Badge className="bg-secondary text-secondary-foreground w-fit capitalize">
                          {normalizedStatus
                            ? normalizedStatus.replace(/_/g, " ")
                            : order.status.replace(/_/g, " ")}
                        </Badge>
                        {!TERMINAL_STATUSES.includes(order.status) && (
                          <span className="text-xs text-muted-foreground">
                            {lastUpdated
                              ? `Updated ${lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · auto-refreshes every 20s`
                              : "Auto-refreshes every 20s"}
                          </span>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="relative">
                      {statusSteps.map((step, index) => {
                        const completed = index <= currentStepIndex;
                        const current = index === currentStepIndex;
                        return (
                          <div
                            key={step.key}
                            className="flex gap-4 pb-8 last:pb-0"
                          >
                            <div
                              className={cn(
                                "relative z-10 w-10 h-10 rounded-full flex items-center justify-center shrink-0 transition-all",
                                completed
                                  ? "text-white"
                                  : "bg-muted text-muted-foreground",
                                current && "ring-4",
                              )}
                              style={
                                completed
                                  ? {
                                      backgroundColor: primaryColor,
                                      ...(current
                                        ? {
                                            boxShadow: `0 0 0 4px ${primaryColor}30`,
                                          }
                                        : {}),
                                    }
                                  : current
                                    ? {
                                        boxShadow: `0 0 0 4px ${primaryColor}30`,
                                      }
                                    : {}
                              }
                            >
                              <step.icon className="w-5 h-5" />
                            </div>
                            <div className="flex-1 pt-1">
                              <h3
                                className={cn(
                                  "font-semibold",
                                  completed
                                    ? "text-foreground"
                                    : "text-muted-foreground",
                                )}
                              >
                                {step.label}
                              </h3>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>

                {order.address && (
                  <Card>
                    <CardHeader className="pb-4">
                      <CardTitle className="font-serif text-lg">
                        Delivery Information
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-start gap-3">
                        <MapPin
                          className="w-5 h-5 text-primary shrink-0 mt-0.5"
                          style={{ color: primaryColor }}
                        />
                        <p className="font-medium">{order.address}</p>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>

              {/* Order Summary */}
              <div className="space-y-6">
                <Card>
                  <CardHeader className="pb-4">
                    <CardTitle className="font-serif text-lg">
                      Order Summary
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {order.items.map((item, i) => (
                      <div
                        key={i}
                        className="flex justify-between items-center"
                      >
                        <div>
                          <p className="font-medium">{item.name}</p>
                          <p className="text-sm text-muted-foreground">
                            Qty: {item.quantity}
                          </p>
                        </div>
                        <p className="font-medium">
                          ${(item.price * item.quantity).toFixed(2)}
                        </p>
                      </div>
                    ))}
                    <div className="pt-4 border-t">
                      <div className="flex justify-between font-semibold text-lg">
                        <span>Total</span>
                        <span>${order.total.toFixed(2)}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
