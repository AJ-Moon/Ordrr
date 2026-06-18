import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Star, Flame } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCart } from "@/contexts/CartContext";
import { toast } from "sonner";
import { fetchJsonWithRetry } from "@/lib/api";
import { useRestaurant } from "@/contexts/RestaurantContext";

type MenuItem = {
  id: number;
  name: string;
  description: string;
  price: number;
  salePrice?: number | null;
  image: string;
  rating: number;
  isSpicy: boolean;
  isPopular: boolean;
  isFeatured?: boolean;
};

export function FeaturedItems() {
  const { addItem } = useCart();
  const navigate = useNavigate();
  const { featuredSectionTitle, featuredSectionSubtitle, currencySymbol } = useRestaurant();

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

  const featuredItems = useMemo(() => {
    const explicit = items.filter((item) => item.isFeatured);
    const fallback = items.filter(
      (item) => item.isPopular || item.rating >= 4.5,
    );
    return (explicit.length ? explicit : fallback).slice(0, 4);
  }, [items]);

  if (loading) {
    return (
      <section className="bg-background py-12 lg:py-16">
        <div className="mx-auto max-w-7xl px-4 lg:px-8">
          <div className="mb-8 text-center">
            <h2 className="font-serif text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              {featuredSectionTitle}
            </h2>
          </div>
          <div className="flex snap-x snap-mandatory gap-6 overflow-x-auto scrollbar-hide pb-2 sm:grid sm:snap-none sm:overflow-visible sm:pb-0 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, idx) => (
              <div
                key={idx}
                className="w-[80vw] max-w-[320px] shrink-0 snap-start rounded-2xl border border-border bg-card sm:w-auto sm:max-w-none"
              >
                <div className="aspect-square animate-pulse rounded-t-2xl bg-muted" />
                <div className="space-y-2 p-4">
                  <div className="h-3 w-1/3 animate-pulse rounded-full bg-muted" />
                  <div className="h-5 w-2/3 animate-pulse rounded-full bg-muted" />
                  <div className="h-3 w-full animate-pulse rounded-full bg-muted" />
                  <div className="h-3 w-4/5 animate-pulse rounded-full bg-muted" />
                  <div className="flex items-center justify-between pt-1">
                    <div className="h-6 w-16 animate-pulse rounded-full bg-muted" />
                    <div className="h-8 w-16 animate-pulse rounded-lg bg-muted" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="bg-background py-12 lg:py-16">
        <div className="mx-auto max-w-7xl px-4 text-center lg:px-8">
          <p className="text-sm text-muted-foreground">
            Could not load featured items.
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

  if (featuredItems.length === 0) return null;

  return (
    <section className="bg-background py-12 lg:py-16">
      <div className="mx-auto max-w-7xl px-4 lg:px-8">
        {/* Section Header */}
        <div className="mb-8 text-center">
          <Badge
            variant="outline"
            className="mb-2 border-primary/30 text-primary"
          >
            <Star className="mr-1 h-3 w-3 fill-current" />
            What&apos;s New
          </Badge>
          <h2 className="font-serif text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            {featuredSectionTitle}
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">
            {featuredSectionSubtitle}
          </p>
        </div>

        {/* Items Grid */}
        <div className="flex snap-x snap-mandatory gap-6 overflow-x-auto scrollbar-hide pb-2 sm:grid sm:snap-none sm:overflow-visible sm:pb-0 sm:grid-cols-2 lg:grid-cols-4">
          {featuredItems.map((item) => (
            <div
              key={item.id}
              className={cn(
                "group relative w-[80vw] max-w-[320px] shrink-0 snap-start overflow-hidden rounded-2xl bg-card border border-border transition-all duration-300",
                "sm:w-auto sm:max-w-none sm:shrink",
                "hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-2",
              )}
            >
              {/* Image */}
              <div className="relative aspect-square overflow-hidden">
                <img
                  src={item.image}
                  alt={item.name}
                  loading="lazy"
                  className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                />

                {/* Badges */}
                <div className="absolute left-3 top-3 flex flex-col gap-2">
                  {item.isFeatured && (
                    <Badge className="bg-secondary text-secondary-foreground">
                      New
                    </Badge>
                  )}
                  {!item.isFeatured && item.isPopular && (
                    <Badge className="bg-secondary text-secondary-foreground">
                      Popular
                    </Badge>
                  )}
                  {item.isSpicy && (
                    <Badge variant="destructive" className="gap-1">
                      <Flame className="h-3 w-3" />
                      Spicy
                    </Badge>
                  )}
                </div>

                {/* Quick Add Button */}
                <Button
                  size="icon"
                  className="absolute bottom-3 right-3 h-10 w-10 rounded-full bg-primary text-primary-foreground opacity-0 shadow-lg transition-all duration-300 hover:scale-110 hover:bg-primary/90 group-hover:opacity-100"
                  onClick={() => {
                    const finalPrice =
                      item.salePrice != null && item.salePrice < item.price
                        ? item.salePrice
                        : item.price;
                    addItem({
                      menuItemId: item.id,
                      name: item.name,
                      price: finalPrice,
                      image: item.image,
                    });
                    toast.success(`${item.name} added to cart`, {
                      action: {
                        label: "View Cart",
                        onClick: () => navigate("/cart"),
                      },
                    });
                  }}
                >
                  <Plus className="h-5 w-5" />
                  <span className="sr-only">Add to cart</span>
                </Button>
              </div>

              {/* Content */}
              <div className="p-4">
                {/* Rating */}
                <div className="mb-2 flex items-center gap-1">
                  <Star className="h-4 w-4 fill-secondary text-secondary" />
                  <span className="text-sm font-medium text-foreground">
                    {item.rating}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    ({Math.round(item.rating * 20)})
                  </span>
                </div>

                <h3 className="font-serif text-lg font-semibold text-card-foreground line-clamp-1">
                  {item.name}
                </h3>
                <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                  {item.description}
                </p>

                {/* Price */}
                <div className="mt-3 flex items-center justify-between">
                  <div className="flex items-baseline gap-2">
                    {item.salePrice != null && item.salePrice < item.price ? (
                      <>
                        <span className="font-serif text-xl font-bold text-primary">
                          {currencySymbol}{item.salePrice.toFixed(2)}
                        </span>
                        <span className="text-sm text-muted-foreground line-through">
                          {currencySymbol}{item.price.toFixed(2)}
                        </span>
                      </>
                    ) : (
                      <span className="font-serif text-xl font-bold text-primary">
                        {currencySymbol}{item.price.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <Button variant="ghost" size="sm" asChild>
                    <Link to="/menu">View</Link>
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* View Menu Button */}
        <div className="mt-10 text-center">
          <Button size="lg" variant="outline" asChild>
            <Link to="/menu">Explore Full Menu</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
