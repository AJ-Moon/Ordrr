import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ShoppingCart, Percent } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchJsonWithRetry } from "@/lib/api";
import { useCart } from "@/contexts/CartContext";
import { toast } from "sonner";
import { useRestaurant } from "@/contexts/RestaurantContext";

type MenuItem = {
  id: number;
  name: string;
  description: string;
  price: number;
  salePrice?: number | null;
  image: string;
  isPopular: boolean;
  isFeatured?: boolean;
};

export function DealsSection() {
  const { addItem } = useCart();
  const navigate = useNavigate();
  const { dealsSectionTitle, dealsSectionSubtitle, currencySymbol } = useRestaurant();
  const {
    data: items = [],
    isLoading: loading,
    isError: error,
    refetch,
  } = useQuery({
    queryKey: ["menu-all"],
    queryFn: () =>
      fetchJsonWithRetry<MenuItem[]>("/api/menu/", undefined, {
        timeoutMs: 15000,
        retries: 1,
      }),
    retry: 0,
    staleTime: 1000 * 60 * 5,
  });

  const deals = useMemo(() => {
    return items
      .filter((item) => item.salePrice != null && item.salePrice < item.price)
      .map((item) => {
        const discountedPrice = Number(item.salePrice);
        const originalPrice = item.price;
        const discount = Math.round(
          ((originalPrice - discountedPrice) / originalPrice) * 100,
        );
        return {
          id: item.id,
          title: item.name,
          description: item.description,
          originalPrice,
          discountedPrice,
          discount,
          image: item.image,
          badge: item.isFeatured
            ? "Featured"
            : item.isPopular
              ? "Popular"
              : "Limited",
          expiresIn: "Limited time",
        };
      })
      .slice(0, 3);
  }, [items]);

  if (loading) {
    return (
      <section className="bg-muted py-12 lg:py-16">
        <div className="mx-auto max-w-7xl px-4 lg:px-8">
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, idx) => (
              <div
                key={idx}
                className="aspect-4/3 animate-pulse rounded-2xl bg-card"
              />
            ))}
          </div>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="bg-muted py-12 lg:py-16">
        <div className="mx-auto max-w-7xl px-4 text-center lg:px-8">
          <p className="text-sm text-muted-foreground">
            Could not load deals right now.
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => refetch()}
          >
            Retry
          </Button>
        </div>
      </section>
    );
  }

  if (deals.length === 0) return null;

  return (
    <section className="bg-muted py-12 lg:py-16">
      <div className="mx-auto max-w-7xl px-4 lg:px-8">
        {/* Section Header */}
        <div className="mb-10 flex flex-col items-start justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <Badge
              variant="secondary"
              className="mb-3 border-primary/20 bg-primary/10 px-3 py-1 text-primary transition-colors hover:bg-primary/20"
            >
              <Percent className="mr-1.5 h-3.5 w-3.5" />
              Limited Time Only
            </Badge>
            <h2 className="font-serif text-4xl font-extrabold tracking-tight sm:text-5xl">
              <span className="bg-gradient-to-r from-primary to-orange-500 bg-clip-text text-transparent">
                {dealsSectionTitle}
              </span>
            </h2>
            <p className="mt-3 max-w-xl text-lg text-muted-foreground">
              {dealsSectionSubtitle}
            </p>
          </div>
          <Button variant="outline" className="group h-10 px-6" asChild>
            <Link to="/menu">
              View All Offers
              <span className="ml-2 transition-transform group-hover:translate-x-1">
                →
              </span>
            </Link>
          </Button>
        </div>

        {/* Deals Grid */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {deals.map((deal) => (
            <div
              key={deal.id}
              className={cn(
                "group relative overflow-hidden rounded-2xl bg-card shadow-sm transition-all duration-300",
                "hover:shadow-xl hover:shadow-primary/10",
              )}
            >
              {/* Image Container */}
              <div className="relative aspect-4/3 overflow-hidden">
                <img
                  src={deal.image}
                  alt={deal.title}
                  className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                />

                {/* Discount Badge */}
                <div className="absolute left-4 top-4">
                  <Badge className="bg-primary text-primary-foreground">
                    {deal.discount}% OFF
                  </Badge>
                </div>

                {/* Type Badge */}
                <div className="absolute right-4 top-4">
                  <Badge
                    variant="secondary"
                    className="bg-accent text-accent-foreground"
                  >
                    {deal.badge}
                  </Badge>
                </div>
              </div>

              {/* Content */}
              <div className="p-5">
                <h3 className="font-serif text-xl font-bold text-card-foreground">
                  {deal.title}
                </h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  {deal.description}
                </p>

                {/* Price */}
                <div className="mt-4 flex items-baseline gap-2">
                  <span className="font-serif text-2xl font-bold text-primary">
                    {currencySymbol}{deal.discountedPrice.toFixed(2)}
                  </span>
                  <span className="text-sm text-muted-foreground line-through">
                    {currencySymbol}{deal.originalPrice.toFixed(2)}
                  </span>
                </div>

                {/* CTA */}
                <div className="mt-4">
                  <Button
                    size="sm"
                    className="w-full gap-2"
                    onClick={() => {
                      addItem({
                        menuItemId: deal.id,
                        name: deal.title,
                        price: deal.discountedPrice,
                        image: deal.image,
                      });
                      toast.success(`${deal.title} added to cart`, {
                        action: {
                          label: "View Cart",
                          onClick: () => navigate("/cart"),
                        },
                      });
                    }}
                  >
                    <ShoppingCart className="h-4 w-4" />
                    Add to Cart
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
