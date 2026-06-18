import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useDebounce } from "@/hooks/use-debounce";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Plus,
  Star,
  Flame,
  Search,
  SlidersHorizontal,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCart } from "@/contexts/CartContext";
import { useRestaurant } from "@/contexts/RestaurantContext";
import { toast } from "sonner";
import { fetchJsonWithRetry } from "@/lib/api";
import { track } from "@/lib/analytics";

const toTitle = (value: string) =>
  value
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (m) => m.toUpperCase());

type MenuItem = {
  id: number;
  category: string;
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

export default function MenuPage() {
  const { addItem } = useCart();
  const { restaurantName } = useRestaurant();
  const navigate = useNavigate();
  const [activeCategory, setActiveCategory] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [priceRange, setPriceRange] = useState([0, 9999]);
  const [sortBy, setSortBy] = useState("popular");
  const [showFilters, setShowFilters] = useState(false);

  const debouncedSearch = useDebounce(searchQuery, 300);
  const lastTrackedResultKey = useRef("");

  const {
    data: rawCategories,
    isLoading: categoriesLoading,
    isError: categoriesError,
    refetch: refetchCategories,
  } = useQuery({
    queryKey: ["categories"],
    queryFn: () =>
      fetchJsonWithRetry<string[]>("/api/menu/categories", undefined, {
        timeoutMs: 15000,
        retries: 1,
      }),
    staleTime: 1000 * 60 * 10,
    retry: 0,
  });

  const categories = [
    { id: "all", name: "All Items" },
    ...(rawCategories ?? []).map((c) => ({ id: c, name: toTitle(c) })),
  ];

  const params = new URLSearchParams();
  if (activeCategory !== "all") params.set("category", activeCategory);
  if (debouncedSearch) params.set("search", debouncedSearch);
  if (sortBy !== "popular") params.set("sort", sortBy);

  const {
    data: allItems = [],
    isLoading: itemsLoading,
    isFetching: itemsFetching,
    isError: itemsError,
    refetch: refetchItems,
  } = useQuery({
    queryKey: ["menu", activeCategory, debouncedSearch, sortBy],
    queryFn: () =>
      fetchJsonWithRetry<MenuItem[]>(`/api/menu/?${params}`, undefined, {
        timeoutMs: 15000,
        retries: 1,
      }),
    retry: 0,
  });

  const filteredItems = allItems.filter((item) => {
    if (item.price < priceRange[0]) return false;
    if (priceRange[1] < 9999 && item.price > priceRange[1]) return false;
    return true;
  });

  const maxPrice = allItems.length > 0
    ? Math.ceil(Math.max(...allItems.map((i) => i.price)))
    : 100;

  useEffect(() => {
    track("menu_viewed")
  }, [])

  useEffect(() => {
    if (itemsLoading || itemsFetching || itemsError) return
    const key = `${activeCategory}|${debouncedSearch}|${sortBy}|${allItems.map((item) => item.id).join(",")}`
    if (lastTrackedResultKey.current === key) return
    lastTrackedResultKey.current = key
    if (activeCategory !== "all") {
      track("category_viewed", { categoryId: activeCategory })
    }
    if (debouncedSearch) {
      track("search_performed", {
        properties: { query: debouncedSearch, resultCount: allItems.length },
      })
    }
    for (const item of allItems.slice(0, 50)) {
      track("item_impression", { itemId: item.id, categoryId: item.category })
    }
  }, [activeCategory, allItems, debouncedSearch, itemsError, itemsFetching, itemsLoading, sortBy])

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="pb-20 md:pb-0">
        {/* Hero */}
        <section className="bg-accent py-12 lg:py-16">
          <div className="mx-auto max-w-7xl px-4 text-center lg:px-8">
            <h1 className="font-serif text-4xl font-bold text-accent-foreground sm:text-5xl">
              {restaurantName} Menu
            </h1>
            <p className="mx-auto mt-4 max-w-2xl text-accent-foreground/70">
              From flame-grilled burgers to wood-fired pizzas, explore flavors
              crafted with passion
            </p>
          </div>
        </section>

        {/* Filters Bar */}
        <section className="sticky top-16 z-40 border-b border-border bg-background/95 backdrop-blur">
          <div className="mx-auto max-w-7xl px-4 py-4 lg:px-8">
            <div className="flex flex-wrap items-center gap-4">
              <div className="relative flex-1 sm:max-w-xs">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder="Search menu..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-10 pl-10"
                />
              </div>

              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="h-10 w-35">
                  <SelectValue placeholder="Sort by" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="popular">Popular</SelectItem>
                  <SelectItem value="rating">Top Rated</SelectItem>
                  <SelectItem value="price-low">Price: Low</SelectItem>
                  <SelectItem value="price-high">Price: High</SelectItem>
                </SelectContent>
              </Select>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowFilters(!showFilters)}
                className="gap-2"
              >
                <SlidersHorizontal className="h-4 w-4" />
                Filters
                {(priceRange[0] > 0 || priceRange[1] < 9999) && (
                  <Badge variant="secondary" className="ml-1 h-5 px-1.5">
                    1
                  </Badge>
                )}
              </Button>

              {/* Refetch indicator */}
              {itemsFetching && !itemsLoading && (
                <Loader2 className="ml-auto h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>

            {showFilters && (
              <div className="mt-4 rounded-lg border border-border bg-card p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-foreground">
                    Price Range
                  </h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setPriceRange([0, 9999])}
                    className="h-auto p-0 text-xs text-muted-foreground"
                  >
                    Reset
                  </Button>
                </div>
                <div className="mt-4">
                  <Slider
                    value={priceRange}
                    onValueChange={setPriceRange}
                    min={0}
                    max={maxPrice}
                    step={1}
                    className="w-full"
                  />
                  <div className="mt-2 flex justify-between text-sm text-muted-foreground">
                    <span>${priceRange[0]}</span>
                    <span>{priceRange[1] >= maxPrice ? "Any" : `$${priceRange[1]}`}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Category Tabs */}
        <section className="border-b border-border bg-background">
          <div className="mx-auto max-w-7xl px-4 lg:px-8">
            <div className="flex gap-1 overflow-x-auto py-3 scrollbar-hide">
              {categoriesLoading && (
                <div className="px-2 py-2 text-sm text-muted-foreground">
                  Loading categories...
                </div>
              )}
              {categories.map((category) => (
                <Button
                  key={category.id}
                  variant={activeCategory === category.id ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setActiveCategory(category.id)}
                  className={cn(
                    "shrink-0 rounded-full px-4",
                    activeCategory === category.id && "shadow-md",
                  )}
                >
                  {category.name}
                </Button>
              ))}
              {categoriesError && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchCategories()}
                >
                  Retry Categories
                </Button>
              )}
            </div>
          </div>
        </section>

        {/* Menu Grid */}
        <section className="py-8 lg:py-12">
          <div className="mx-auto max-w-7xl px-4 lg:px-8">
            {itemsLoading ? (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-72 animate-pulse rounded-2xl bg-muted"
                  />
                ))}
              </div>
            ) : itemsError ? (
              <div className="py-12 text-center">
                <p className="text-lg text-muted-foreground">
                  Menu failed to load.
                </p>
                <Button variant="outline" onClick={() => refetchItems()}>
                  Retry
                </Button>
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="py-12 text-center">
                <p className="text-lg text-muted-foreground">No items found</p>
                <Button
                  variant="link"
                  onClick={() => {
                    setActiveCategory("all");
                    setSearchQuery("");
                    setPriceRange([0, 20]);
                  }}
                >
                  Clear all filters
                </Button>
              </div>
            ) : (
              <div
                className={cn(
                  "grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 transition-opacity duration-200",
                  itemsFetching && "opacity-60 pointer-events-none",
                )}
              >
                {filteredItems.map((item) => (
                  <div
                    key={item.id}
                    className={cn(
                      "group overflow-hidden rounded-2xl border border-border bg-card transition-all duration-300",
                      "hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5",
                    )}
                  >
                    <div className="relative aspect-4/3 overflow-hidden">
                      <img
                        src={item.image}
                        alt={item.name}
                        loading="lazy"
                        className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                      />
                      <div className="absolute left-3 top-3 flex flex-col gap-2">
                        {item.isPopular && (
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
                      <Button
                        size="icon"
                        className="absolute bottom-3 right-3 h-10 w-10 rounded-full opacity-0 shadow-lg transition-all group-hover:opacity-100"
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
                        }}>
                        <Plus className="h-5 w-5" />
                        <span className="sr-only">Add to cart</span>
                      </Button>
                    </div>
                    <div className="p-4">
                      <div className="mb-2 flex items-center gap-1">
                        <Star className="h-4 w-4 fill-secondary text-secondary" />
                        <span className="text-sm font-medium">
                          {item.rating}
                        </span>
                      </div>
                      <h3 className="font-serif text-lg font-semibold text-card-foreground line-clamp-1">
                        {item.name}
                      </h3>
                      <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                        {item.description}
                      </p>
                      <div className="mt-3 flex items-center justify-between">
                        <div className="flex items-baseline gap-2">
                          {item.salePrice != null &&
                          item.salePrice < item.price ? (
                            <>
                              <span className="font-serif text-xl font-bold text-primary">
                                ${item.salePrice.toFixed(2)}
                              </span>
                              <span className="text-sm text-muted-foreground line-through">
                                ${item.price.toFixed(2)}
                              </span>
                            </>
                          ) : (
                            <span className="font-serif text-xl font-bold text-primary">
                              ${item.price.toFixed(2)}
                            </span>
                          )}
                        </div>
                        <Button
                          size="sm"
                          onClick={() => {
                            const finalPrice =
                              item.salePrice != null &&
                              item.salePrice < item.price
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
                          Add to Cart
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
