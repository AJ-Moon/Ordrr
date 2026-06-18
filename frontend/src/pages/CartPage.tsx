import { Link, useNavigate } from "react-router-dom";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  ShoppingCart,
  Trash2,
  Plus,
  Minus,
  ArrowRight,
  UtensilsCrossed,
} from "lucide-react";
import { useCart } from "@/contexts/CartContext";
import { useRestaurant } from "@/contexts/RestaurantContext";
import { MissionBundleCard } from "@/components/MissionBundleCard";

export default function CartPage() {
  const { items, removeItem, updateQty, total, clearCart } = useCart();
  const { deliveryCharge, minOrderAmount, currencySymbol } = useRestaurant();
  const navigate = useNavigate();

  const deliveryLabel =
    deliveryCharge > 0 ? `${currencySymbol}${deliveryCharge.toFixed(2)}` : "Free delivery";
  const estimatedTotal = total + deliveryCharge;
  const belowMinimum = minOrderAmount > 0 && total < minOrderAmount;

  if (items.length === 0) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <main className="pb-20 md:pb-0">
          <div className="mx-auto flex max-w-lg flex-col items-center justify-center px-4 py-24 text-center">
            <div className="mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-muted">
              <ShoppingCart className="h-12 w-12 text-muted-foreground" />
            </div>
            <h1 className="mb-2 font-serif text-2xl font-bold text-foreground">
              Your cart is empty
            </h1>
            <p className="mb-8 text-muted-foreground">
              Looks like you haven't added anything yet. Browse our menu to get
              started.
            </p>
            <Button asChild size="lg">
              <Link to="/menu">
                <UtensilsCrossed className="mr-2 h-5 w-5" />
                Explore Menu
              </Link>
            </Button>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="pb-24 md:pb-0">
        <div className="mx-auto max-w-4xl px-4 py-8 lg:px-8">
          <div className="mb-6 flex items-center justify-between">
            <h1 className="font-serif text-2xl font-bold text-foreground sm:text-3xl">
              Your Cart
              <span className="ml-2 text-base font-normal text-muted-foreground">
                ({items.length} {items.length === 1 ? "item" : "items"})
              </span>
            </h1>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearCart}
              className="text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="mr-1 h-4 w-4" />
              Clear cart
            </Button>
          </div>

          <div className="grid gap-8 lg:grid-cols-3">
            {/* Cart Items */}
            <div className="lg:col-span-2 space-y-3">
              <MissionBundleCard />
              {items.map((item) => (
                <div
                  key={item.menuItemId}
                  className="flex gap-4 rounded-xl border border-border bg-card p-4"
                >
                  <div className="h-20 w-20 shrink-0 overflow-hidden rounded-lg bg-muted">
                    {item.image ? (
                      <img
                        src={item.image}
                        alt={item.name}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center">
                        <UtensilsCrossed className="h-8 w-8 text-muted-foreground" />
                      </div>
                    )}
                  </div>
                  <div className="flex flex-1 flex-col justify-between">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-medium text-foreground">
                        {item.name}
                      </h3>
                      <button
                        onClick={() => removeItem(item.menuItemId)}
                        className="shrink-0 text-muted-foreground hover:text-destructive"
                        aria-label="Remove item"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1 rounded-full border border-border">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 rounded-full"
                          onClick={() =>
                            updateQty(item.menuItemId, item.quantity - 1)
                          }
                        >
                          <Minus className="h-3 w-3" />
                        </Button>
                        <span className="w-6 text-center text-sm font-semibold">
                          {item.quantity}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 rounded-full"
                          onClick={() =>
                            updateQty(item.menuItemId, item.quantity + 1)
                          }
                        >
                          <Plus className="h-3 w-3" />
                        </Button>
                      </div>
                      <div className="text-right">
                        <div className="font-semibold text-foreground">
                          {currencySymbol}{(item.price * item.quantity).toFixed(2)}
                        </div>
                        {item.quantity > 1 && (
                          <div className="text-xs text-muted-foreground">
                            {currencySymbol}{item.price.toFixed(2)} each
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              <div className="pt-2">
                <Button variant="outline" asChild>
                  <Link to="/menu">+ Add more items</Link>
                </Button>
              </div>
            </div>

            {/* Order Summary */}
            <div className="lg:col-span-1">
              <div className="sticky top-24 rounded-xl border border-border bg-card p-6">
                <h2 className="mb-4 font-serif text-lg font-semibold text-foreground">
                  Order Summary
                </h2>
                <div className="space-y-3 text-sm">
                  {items.map((item) => (
                    <div
                      key={item.menuItemId}
                      className="flex justify-between text-muted-foreground"
                    >
                      <span>
                        {item.name} × {item.quantity}
                      </span>
                      <span>{currencySymbol}{(item.price * item.quantity).toFixed(2)}</span>
                    </div>
                  ))}
                  <Separator />
                  <div className="flex justify-between font-semibold text-foreground text-base">
                    <span>Subtotal</span>
                    <span>{currencySymbol}{total.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>Delivery</span>
                    <span>{deliveryLabel}</span>
                  </div>
                  <div className="flex justify-between font-semibold text-foreground text-base">
                    <span>Estimated total</span>
                    <span>{currencySymbol}{estimatedTotal.toFixed(2)}</span>
                  </div>
                  {belowMinimum && (
                    <p className="text-xs font-medium text-amber-600">
                      Minimum order: {currencySymbol}{minOrderAmount.toFixed(2)}
                    </p>
                  )}
                </div>
                <Button
                  className="mt-6 w-full"
                  size="lg"
                  onClick={() => navigate("/checkout")}
                >
                  Proceed to Checkout
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
