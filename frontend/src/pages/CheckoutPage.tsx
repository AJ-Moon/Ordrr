import { useState, useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import { SearchBox } from "@mapbox/search-js-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, ShoppingCart, Star, Loader2, PenLine } from "lucide-react";
import { useCart } from "@/contexts/CartContext";
import { useAuth } from "@/contexts/AuthContext";
import { useRestaurant } from "@/contexts/RestaurantContext";
import { toast } from "sonner";
import { getCartId, getSessionId, getVisitorId, track } from "@/lib/analytics";

interface Branch {
  id: number;
  name: string;
  city: string;
  isOpen: boolean;
}

interface RewardSettings {
  mode: string;
  minRedeem: number;
  conversionRate: number;
}

export default function CheckoutPage() {
  const { items, total, clearCart } = useCart();
  const { user, token } = useAuth();
  const { deliveryCharge, minOrderAmount, currencySymbol, cashOnDelivery } = useRestaurant();
  const navigate = useNavigate();

  const [branches, setBranches] = useState<Branch[]>([]);
  const [rewardSettings, setRewardSettings] = useState<RewardSettings | null>(
    null,
  );
  const [userPoints, setUserPoints] = useState(0);

  // Form state
  const [guestName, setGuestName] = useState("");
  const [guestEmail, setGuestEmail] = useState("");
  const [guestPhone, setGuestPhone] = useState(user?.phone || "");
  const [address, setAddress] = useState("");
  const [orderType, setOrderType] = useState<"delivery" | "pickup">(
    "delivery",
  );
  const [paymentMethod, setPaymentMethod] = useState(cashOnDelivery ? "cash" : "card");
  const [branchId, setBranchId] = useState<number | undefined>(undefined);
  const [notes, setNotes] = useState("");
  const [pointsToRedeem, setPointsToRedeem] = useState(0);
  const [privateOfferCode, setPrivateOfferCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [customerLat, setCustomerLat] = useState<number | null>(null);
  const [customerLng, setCustomerLng] = useState<number | null>(null);
  const [deliveryStatus, setDeliveryStatus] = useState<"idle" | "checking" | "ok" | "outside">("idle");
  // Prevent the empty-cart redirect from firing after a successful order submission
  const submittedRef = useRef(false);
  const checkoutTrackedRef = useRef(false);

  useEffect(() => {
    if (checkoutTrackedRef.current) return
    checkoutTrackedRef.current = true
    track("checkout_started", {
      cartId: getCartId(),
      properties: { itemCount: items.length, displayedTotal: total },
    })
  }, [items.length, total])

  useEffect(() => {
    if (items.length === 0 && !submittedRef.current) {
      navigate("/cart");
    }
  }, [items, navigate]);

  useEffect(() => {
    if (orderType === "delivery" && customerLat !== null && customerLng !== null) {
      setDeliveryStatus("checking");
      const timer = setTimeout(() => {
        fetch("/api/check-delivery", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ customerLat, customerLng }),
        })
          .then((r) => r.json())
          .then((data) => {
             if (data.configured === false || data.withinRadius) {
                setDeliveryStatus("ok");
             } else {
                setDeliveryStatus("outside");
                setOrderType("pickup");
                toast.error("Outside delivery zone — pickup only");
             }
          })
          .catch(() => setDeliveryStatus("idle"));
      }, 300);
      return () => clearTimeout(timer);
    } else {
      setDeliveryStatus("idle");
    }
  }, [customerLat, customerLng, orderType]);

  useEffect(() => {
    fetch("/api/branches/")
      .then((r) => r.json())
      .then((data) => {
        setBranches(data.filter((b: Branch) => b.isOpen));
      })
      .catch(() => {});

    if (user && token) {
      fetch("/api/rewards/points", {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => r.json())
        .then((d) => setUserPoints(d.points || 0))
        .catch(() => {});

      // Public endpoint — no admin auth needed
      fetch("/api/rewards/settings")
        .then((r) => r.json())
        .then((d) => setRewardSettings(d))
        .catch(() => {});
    }
  }, [user, token]);

  const effectiveDelivery = orderType === "delivery" ? deliveryCharge : 0;
  const belowMinimum = minOrderAmount > 0 && total < minOrderAmount;

  const pointsDiscount =
    rewardSettings &&
    userPoints >= rewardSettings.minRedeem &&
    pointsToRedeem >= rewardSettings.minRedeem
      ? Math.min(pointsToRedeem * rewardSettings.conversionRate, total * 0.5)
      : 0;

  const finalTotal = Math.max(0, total + effectiveDelivery - pointsDiscount);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (items.length === 0) return;

    if (!user && !guestName.trim()) {
      toast.error("Please enter your name");
      return;
    }
    if (!user && !guestPhone.trim()) {
      toast.error("Please enter your phone number");
      return;
    }
    if (orderType === "delivery" && !address.trim()) {
      toast.error("Please enter your delivery address");
      return;
    }
    if (orderType === "pickup" && !branchId) {
      toast.error("Please select a branch for pickup");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        items: items.map((i) => ({
          menuItemId: i.menuItemId,
          name: i.name,
          quantity: i.quantity,
          price: i.price,
        })),
        orderType,
        paymentMethod,
        address,
        branchId,
        notes: notes.trim(),
        pointsToRedeem,
        privateOfferCode: privateOfferCode.trim() || undefined,
        customerLat,
        customerLng,
        cartId: getCartId(),
        visitorId: getVisitorId(),
        sessionId: getSessionId(),
      };

      if (!user) {
        payload.guestName = guestName.trim();
        payload.guestEmail = guestEmail.trim();
        payload.guestPhone = guestPhone.trim();
      }

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) headers.Authorization = `Bearer ${token}`;

      const res = await fetch("/api/orders/", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to place order");
      }

      const order = await res.json();
      track("checkout_step_completed", {
        cartId: order.cartId,
        orderId: order.id,
        properties: { step: "ORDER_CONFIRMED", total: order.total, currency: order.currency },
        consentState: "essential",
      })
      submittedRef.current = true;
      clearCart();
      const trackPhone = !user ? guestPhone.trim() : (user.phone || "");
      navigate(`/order-confirmation/${order.id}`, { state: { order, trackPhone } });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to place order";
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (items.length === 0 && !submittedRef.current) return null;

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="pb-24 md:pb-0">
        <div className="mx-auto max-w-4xl px-4 py-8 lg:px-8">
          <div className="mb-6 flex items-center gap-3">
            <Button variant="ghost" size="icon" asChild>
              <Link to="/cart">
                <ArrowLeft className="h-5 w-5" />
              </Link>
            </Button>
            <h1 className="font-serif text-2xl font-bold text-foreground">
              Checkout
            </h1>
          </div>

          <form onSubmit={handleSubmit} className="grid gap-8 lg:grid-cols-3">
            {/* Left — Details */}
            <div className="lg:col-span-2 space-y-6">
              {/* Guest / User Info */}
              {!user ? (
                <Card>
                  <CardContent className="pt-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <h2 className="font-semibold text-foreground">
                        Your Details
                      </h2>
                      <Link
                        to="/login"
                        className="text-sm text-primary hover:underline"
                      >
                        Login for faster checkout
                      </Link>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <Label htmlFor="guestName">Full Name *</Label>
                        <Input
                          id="guestName"
                          placeholder="John Doe"
                          value={guestName}
                          onChange={(e) => setGuestName(e.target.value)}
                          required
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="guestPhone">Phone Number *</Label>
                        <Input
                          id="guestPhone"
                          type="tel"
                          placeholder="+1 234 567 8900"
                          value={guestPhone}
                          onChange={(e) => setGuestPhone(e.target.value)}
                          required
                        />
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="guestEmail">Email (optional)</Label>
                      <Input
                        id="guestEmail"
                        type="email"
                        placeholder="you@example.com"
                        value={guestEmail}
                        onChange={(e) => setGuestEmail(e.target.value)}
                      />
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <Card>
                  <CardContent className="pt-6">
                    <h2 className="mb-2 font-semibold text-foreground">
                      Ordering as
                    </h2>
                    <p className="text-muted-foreground">
                      {user.firstName} {user.lastName} · {user.email}
                    </p>
                    {user.phone && (
                      <p className="text-sm text-muted-foreground">
                        {user.phone}
                      </p>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Order Type */}
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <h2 className="font-semibold text-foreground">Order Type</h2>
                  <div className="grid grid-cols-2 gap-2">
                    {(["delivery", "pickup"] as const).map((type) => (
                      <button
                        key={type}
                        type="button"
                        onClick={() => {
                          setOrderType(type);
                          setBranchId(undefined);
                        }}
                        className={`rounded-lg border p-3 text-sm font-medium capitalize transition-colors ${
                          orderType === type
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border bg-card text-muted-foreground hover:border-primary/50"
                        }`}
                      >
                        {type}
                      </button>
                    ))}
                  </div>

                  {orderType === "delivery" && (
                    <div className="space-y-1.5">
                      <Label htmlFor="address">Delivery Address *</Label>
                      <div className="relative z-50">
                        <SearchBox
                          accessToken={import.meta.env.VITE_MAPBOX_TOKEN || ""}
                          options={{ language: "en" }}
                          value={address}
                          onChange={(value) => setAddress(value)}
                          onRetrieve={(res) => {
                            const feature = res.features[0];
                            if (feature) {
                              setCustomerLng(feature.geometry.coordinates[0]);
                              setCustomerLat(feature.geometry.coordinates[1]);
                              setAddress(feature.properties.full_address || feature.properties.name || "");
                            }
                          }}
                        />
                      </div>
                      {deliveryStatus === "checking" && (
                        <div className="flex items-center text-sm text-muted-foreground mt-1">
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Checking delivery area...
                        </div>
                      )}
                      {deliveryStatus === "ok" && (
                        <div className="flex items-center text-sm text-green-600 mt-1 font-medium">
                          ✅ We deliver to your area
                        </div>
                      )}
                      {deliveryStatus === "outside" && (
                        <div className="flex items-center text-sm text-red-600 mt-1 font-medium">
                          ❌ Outside delivery zone — pickup only
                        </div>
                      )}
                    </div>
                  )}

                  {branches.length > 0 && (
                    <div className="space-y-1.5">
                      <Label>
                        Branch
                        {orderType === "pickup" && (
                          <span className="ml-1 text-destructive">*</span>
                        )}
                      </Label>
                      <Select
                        value={branchId?.toString() || ""}
                        onValueChange={(v) => setBranchId(parseInt(v))}
                      >
                        <SelectTrigger
                          className={(
                            orderType === "pickup" && !branchId
                              ? "border-destructive/50 focus:ring-destructive/30"
                              : ""
                          )}
                        >
                          <SelectValue
                            placeholder={
                              orderType === "pickup"
                                ? "Select pickup branch *"
                                : "Select branch (optional)"
                            }
                          />
                        </SelectTrigger>
                        <SelectContent>
                          {branches.map((b) => (
                            <SelectItem key={b.id} value={b.id.toString()}>
                              {b.name} — {b.city}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {orderType === "pickup" && !branchId && (
                        <p className="text-xs text-destructive">
                          Please select a branch to pick up your order from.
                        </p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Payment */}
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <h2 className="font-semibold text-foreground">
                    Payment Method
                  </h2>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {[
                      ...(cashOnDelivery ? [{ value: "cash", label: "Cash on Delivery" }] : []),
                      { value: "card", label: "Card (at door)" },
                    ].map((pm) => (
                      <button
                        key={pm.value}
                        type="button"
                        onClick={() => setPaymentMethod(pm.value)}
                        className={`rounded-lg border p-3 text-left text-sm font-medium transition-colors ${
                          paymentMethod === pm.value
                            ? "border-primary bg-primary/5 text-primary"
                            : "border-border bg-card text-muted-foreground hover:border-primary/50"
                        }`}
                      >
                        {pm.label}
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Points Redemption */}
              {user &&
                rewardSettings?.mode === "points" &&
                userPoints >= rewardSettings.minRedeem && (
                  <Card>
                    <CardContent className="pt-6 space-y-3">
                      <div className="flex items-center gap-2">
                        <Star className="h-5 w-5 text-secondary" />
                        <h2 className="font-semibold text-foreground">
                          Redeem Points
                        </h2>
                        <Badge variant="secondary">
                          {userPoints} pts available
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {rewardSettings.conversionRate} currency per point. Min:{" "}
                        {rewardSettings.minRedeem} pts.
                      </p>
                      <div className="flex items-center gap-3">
                        <Input
                          type="number"
                          min={0}
                          max={userPoints}
                          step={rewardSettings.minRedeem}
                          value={pointsToRedeem}
                          onChange={(e) =>
                            setPointsToRedeem(parseInt(e.target.value) || 0)
                          }
                          className="max-w-[140px]"
                        />
                        <span className="text-sm text-muted-foreground">
                          = {currencySymbol}{pointsDiscount.toFixed(2)} discount
                        </span>
                      </div>
                    </CardContent>
                  </Card>
                )}

              {/* Notes */}
              <Card className="border-dashed border-2 border-muted hover:border-primary/40 transition-colors">
                <CardContent className="pt-6 space-y-3">
                  <div className="flex items-center gap-2">
                    <PenLine className="h-4 w-4 text-primary" />
                    <h2 className="font-semibold text-foreground">Special Instructions</h2>
                    <span className="text-xs text-muted-foreground ml-auto">Optional</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Allergies, spice level, extra sauce, ring the bell — let us know anything!
                  </p>
                  <div className="relative">
                    <Textarea
                      id="notes"
                      placeholder="e.g. No onions, extra spicy, please knock on arrival..."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value.slice(0, 300))}
                      rows={3}
                      className="resize-none pr-2"
                    />
                    <span className={`absolute bottom-2 right-3 text-xs ${
                      notes.length > 250 ? "text-amber-500" : "text-muted-foreground/60"
                    }`}>
                      {notes.length}/300
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Right — Order Summary */}
            <div className="lg:col-span-1">
              <div className="sticky top-24 rounded-xl border border-border bg-card p-6 space-y-4">
                <h2 className="font-serif text-lg font-semibold text-foreground flex items-center gap-2">
                  <ShoppingCart className="h-5 w-5" />
                  Order Summary
                </h2>

                <div className="space-y-2 text-sm">
                  {items.map((item) => (
                    <div
                      key={item.menuItemId}
                      className="flex justify-between text-muted-foreground"
                    >
                      <span className="flex-1 pr-2">
                        {item.name} × {item.quantity}
                      </span>
                      <span className="shrink-0">
                        {currencySymbol}{(item.price * item.quantity).toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>

                <Separator />

                <div className="space-y-2 text-sm">
                  <div className="flex justify-between text-muted-foreground">
                    <span>Subtotal</span>
                    <span>{currencySymbol}{total.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>Delivery</span>
                    <span>
                      {orderType === "delivery"
                        ? effectiveDelivery > 0
                          ? `${currencySymbol}${effectiveDelivery.toFixed(2)}`
                          : "Free delivery"
                        : "N/A"}
                    </span>
                  </div>
                  {pointsDiscount > 0 && (
                    <div className="flex justify-between text-green-600">
                      <span>Points discount</span>
                      <span>-{currencySymbol}{pointsDiscount.toFixed(2)}</span>
                    </div>
                  )}
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="privateOfferCode">Private offer code</Label>
                  <Input
                    id="privateOfferCode"
                    placeholder="Optional"
                    value={privateOfferCode}
                    onChange={(event) => setPrivateOfferCode(event.target.value.toUpperCase())}
                  />
                  <p className="text-xs text-muted-foreground">Validated securely when the order is placed.</p>
                </div>

                {belowMinimum && (
                  <p className="text-xs font-medium text-amber-600">
                    Minimum order: {currencySymbol}{minOrderAmount.toFixed(2)}
                  </p>
                )}

                <Separator />

                <div className="flex justify-between font-semibold text-foreground text-base">
                  <span>Total</span>
                  <span>{currencySymbol}{finalTotal.toFixed(2)}</span>
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  size="lg"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Placing Order...
                    </>
                  ) : (
                    "Place Order"
                  )}
                </Button>

                <p className="text-center text-xs text-muted-foreground">
                  By placing your order you agree to our{" "}
                  <Link to="/terms" className="underline">
                    terms
                  </Link>
                  .
                </p>
              </div>
            </div>
          </form>
        </div>
      </main>
      <Footer />
    </div>
  );
}
