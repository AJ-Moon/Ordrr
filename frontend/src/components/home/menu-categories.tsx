import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight, UtensilsCrossed } from "lucide-react";
import { fetchJsonWithRetry } from "@/lib/api";
import { useRestaurant } from "@/contexts/RestaurantContext";

type MenuItem = {
  id: number;
  category: string;
  image: string;
};

const fallbackImages = [
  "/images/hero-burger.jpg",
  "/images/hero-pizza.jpg",
  "/images/hero-salad.jpg",
];

const toTitle = (value: string) =>
  value
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (m) => m.toUpperCase());

export function MenuCategories() {
  const { primaryColor } = useRestaurant();
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

  const categories = useMemo(() => {
    const grouped = new Map<
      string,
      { id: string; name: string; image: string; itemCount: number }
    >();
    items.forEach((item, index) => {
      const existing = grouped.get(item.category);
      if (existing) {
        existing.itemCount += 1;
        if (!existing.image && item.image) existing.image = item.image;
        return;
      }
      grouped.set(item.category, {
        id: item.category,
        name: toTitle(item.category),
        image: item.image || fallbackImages[index % fallbackImages.length],
        itemCount: 1,
      });
    });
    return Array.from(grouped.values()).slice(0, 6);
  }, [items]);

  if (loading) {
    return (
      <section className="bg-background py-10 lg:py-14">
        <div className="mx-auto max-w-7xl px-4 lg:px-8">
          <div className="mb-6 text-center">
            <h2 className="font-serif text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              Explore Our Menu
            </h2>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {Array.from({ length: 6 }).map((_, idx) => (
              <div
                key={idx}
                className="h-11 w-28 shrink-0 animate-pulse rounded-full bg-muted"
              />
            ))}
          </div>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="bg-background py-10 lg:py-14">
        <div className="mx-auto max-w-7xl px-4 text-center lg:px-8">
          <p className="text-sm text-muted-foreground">
            Could not load menu categories.
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

  if (categories.length === 0) return null;

  return (
    <section className="bg-background py-10 lg:py-14">
      <div className="mx-auto max-w-7xl px-4 lg:px-8">
        {/* Section Header */}
        <div className="mb-6 text-center">
          <h2 className="font-serif text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Explore Our Menu
          </h2>
          <p className="mx-auto mt-2 max-w-2xl text-muted-foreground">
            From flame-grilled burgers to wood-fired pizzas, discover flavors
            that make every bite memorable.
          </p>
        </div>

        {/* Pill Buttons — horizontal scroll */}
        <div className="flex gap-3 overflow-x-auto scrollbar-hide pb-2">
          {categories.map((category) => (
            <Link
              key={category.id}
              to={`/menu?category=${encodeURIComponent(category.id)}`}
              className="flex shrink-0 items-center gap-2 rounded-full border border-border bg-card px-5 py-2.5 text-sm font-medium text-foreground shadow-sm transition-all duration-200 hover:shadow-md hover:text-primary-foreground"
              style={{ "--pill-hover": primaryColor } as React.CSSProperties}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLAnchorElement).style.backgroundColor =
                  primaryColor;
                (e.currentTarget as HTMLAnchorElement).style.borderColor =
                  primaryColor;
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLAnchorElement).style.backgroundColor =
                  "";
                (e.currentTarget as HTMLAnchorElement).style.borderColor = "";
              }}
            >
              <UtensilsCrossed className="h-4 w-4 shrink-0 text-primary" />
              {category.name}
              <span className="rounded-full bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                {category.itemCount}
              </span>
            </Link>
          ))}
        </div>

        {/* Full-width View Full Menu CTA */}
        <div className="mt-6">
          <Button
            size="lg"
            className="w-full gap-2 text-base font-semibold"
            style={{ backgroundColor: primaryColor }}
            asChild
          >
            <Link to="/menu">
              View Full Menu
              <ArrowRight className="h-5 w-5" />
            </Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
