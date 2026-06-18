import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Link } from "react-router-dom";
import { Star, Zap, Bell, ShoppingBag } from "lucide-react";
import { useRestaurant } from "@/contexts/RestaurantContext";

export function AppPromo() {
  const { promoHeadline, promoBody } = useRestaurant();
  return (
    <section className="bg-accent py-12 lg:py-16">
      <div className="mx-auto max-w-7xl px-4 lg:px-8">
        <div className="grid items-center gap-8 lg:grid-cols-2 lg:gap-12">
          {/* Phone Mockup */}
          <div className="relative order-2 lg:order-1">
            <div className="relative mx-auto h-[500px] w-[260px]">
              {/* Phone Frame */}
              <div className="absolute inset-0 rounded-[3rem] border-[8px] border-accent-foreground/10 bg-accent-foreground/5 shadow-2xl">
                {/* Screen Content */}
                <div className="absolute inset-2 overflow-hidden rounded-[2.5rem] bg-background">
                  {/* App Header */}
                  <div className="bg-primary p-4 pb-12">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-primary-foreground/70">
                          Good evening
                        </p>
                        <p className="font-serif text-lg font-bold text-primary-foreground">
                          John Doe
                        </p>
                      </div>
                      <div className="h-10 w-10 rounded-full bg-primary-foreground/20" />
                    </div>
                  </div>

                  {/* Floating Card */}
                  <div className="-mt-8 mx-3 rounded-xl bg-card p-4 shadow-lg">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-muted-foreground">
                          Your Balance
                        </p>
                        <p className="font-serif text-2xl font-bold text-primary">
                          750 pts
                        </p>
                      </div>
                      <Button size="sm" className="h-8">
                        Redeem
                      </Button>
                    </div>
                  </div>

                  {/* Quick Actions */}
                  <div className="mt-4 grid grid-cols-4 gap-2 px-3">
                    {["Order", "Menu", "Track", "Offers"].map((action) => (
                      <div
                        key={action}
                        className="flex flex-col items-center gap-1 rounded-lg bg-muted p-2"
                      >
                        <div className="h-6 w-6 rounded-full bg-primary/20" />
                        <span className="text-[10px] text-muted-foreground">
                          {action}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Featured Items */}
                  <div className="mt-4 px-3">
                    <p className="mb-2 text-xs font-semibold text-foreground">
                      For You
                    </p>
                    <div className="flex gap-2 overflow-hidden">
                      <div className="h-20 w-20 shrink-0 rounded-lg bg-muted" />
                      <div className="h-20 w-20 shrink-0 rounded-lg bg-muted" />
                      <div className="h-20 w-20 shrink-0 rounded-lg bg-muted" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Notch */}
              <div className="absolute left-1/2 top-4 h-6 w-24 -translate-x-1/2 rounded-full bg-accent-foreground/10" />
            </div>

            {/* Floating Badges */}
            <div className="absolute left-0 top-20 rounded-lg bg-card p-3 shadow-lg lg:-left-8">
              <div className="flex items-center gap-2">
                <Star className="h-5 w-5 fill-secondary text-secondary" />
                <span className="text-sm font-medium text-foreground">
                  4.9 Rating
                </span>
              </div>
            </div>
            <div className="absolute bottom-32 right-0 rounded-lg bg-card p-3 shadow-lg lg:-right-8">
              <div className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-secondary" />
                <span className="text-sm font-medium text-foreground">
                  Fast Ordering
                </span>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="order-1 lg:order-2">
            <Badge
              variant="secondary"
              className="mb-4 bg-secondary text-secondary-foreground"
            >
              <ShoppingBag className="mr-1 h-3 w-3" />
              Order Online
            </Badge>
            <h2 className="font-serif text-3xl font-bold tracking-tight text-accent-foreground sm:text-4xl lg:text-5xl">
              {promoHeadline}
            </h2>
            <p className="mt-4 text-lg leading-relaxed text-accent-foreground/70">
              {promoBody}
            </p>

            {/* Features */}
            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Zap className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold text-accent-foreground">
                    1-Tap Reorder
                  </h3>
                  <p className="text-sm text-accent-foreground/70">
                    Reorder your favorites instantly
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Bell className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold text-accent-foreground">
                    Push Notifications
                  </h3>
                  <p className="text-sm text-accent-foreground/70">
                    Exclusive deals sent to your phone
                  </p>
                </div>
              </div>
            </div>

            {/* CTA Button */}
            <div className="mt-8">
              <Button size="lg" className="gap-2 px-8" asChild>
                <Link to="/menu">
                  <ShoppingBag className="h-5 w-5" />
                  Start Your Order
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
