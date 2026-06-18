import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { MapPin, Clock, Phone, Navigation, Search, LocateFixed } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useRestaurant } from "@/contexts/RestaurantContext";

type Branch = {
  id: number;
  name: string;
  address: string;
  city: string;
  phone: string;
  hours: string;
  isOpen: boolean;
};

const fullAddress = (b: Branch) => `${b.address}, ${b.city}`;

export default function BranchesPage() {
  const { restaurantName } = useRestaurant();
  const navigate = useNavigate();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [userLoc, setUserLoc] = useState<{ lat: number; lng: number } | null>(null);
  const [locating, setLocating] = useState(false);

  useEffect(() => {
    fetch("/api/branches/")
      .then((r) => r.json())
      .then((data: Branch[]) => setBranches(data))
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return branches;
    return branches.filter((b) =>
      [b.name, b.address, b.city].some((f) => (f || "").toLowerCase().includes(q)),
    );
  }, [branches, query]);

  // The active branch drives the map; default to the first visible branch.
  const activeBranch =
    filtered.find((b) => b.id === activeId) ?? filtered[0] ?? null;

  // Google Maps embeds need no API key. With the visitor's location we can
  // surface real turn-by-turn directions instead of a plain location pin.
  const mapSrc = activeBranch
    ? `https://www.google.com/maps?q=${encodeURIComponent(fullAddress(activeBranch))}&output=embed`
    : null;

  const directionsUrl = (b: Branch) => {
    const destination = encodeURIComponent(fullAddress(b));
    if (userLoc) {
      return `https://www.google.com/maps/dir/?api=1&origin=${userLoc.lat},${userLoc.lng}&destination=${destination}`;
    }
    return `https://www.google.com/maps/dir/?api=1&destination=${destination}`;
  };

  const useMyLocation = () => {
    if (!("geolocation" in navigator)) {
      toast.error("Location services are not available in this browser.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLoc({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocating(false);
        toast.success("Directions will now start from your location.");
      },
      () => {
        setLocating(false);
        toast.error("Could not access your location. Please allow location access.");
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="pb-20 md:pb-0">
        {/* Hero */}
        <section className="bg-accent py-12 lg:py-16">
          <div className="mx-auto max-w-7xl px-4 text-center lg:px-8">
            <h1 className="font-serif text-4xl font-bold text-accent-foreground sm:text-5xl">
              Our Locations
            </h1>
            <p className="mx-auto mt-4 max-w-2xl text-accent-foreground/70">
              Find {restaurantName} near you. Dine in, pick up, or get it delivered.
            </p>
          </div>
        </section>

        {/* Search & Map Section */}
        <section className="py-8 lg:py-12">
          <div className="mx-auto max-w-7xl px-4 lg:px-8">
            <div className="grid gap-8 lg:grid-cols-5">
              {/* Branch List */}
              <div className="lg:col-span-2">
                {/* Search */}
                <div className="relative mb-6">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    type="search"
                    placeholder="Search by location or zip code"
                    className="h-12 pl-10"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>

                {/* Branch Cards */}
                <div className="space-y-4">
                  {isLoading
                    ? Array.from({ length: 3 }).map((_, i) => (
                        <div
                          key={i}
                          className="rounded-xl border bg-card p-5 space-y-3"
                        >
                          <div className="flex items-center gap-2">
                            <Skeleton className="h-5 w-36" />
                            <Skeleton className="h-5 w-14 rounded-full" />
                          </div>
                          <Skeleton className="h-4 w-56" />
                          <Skeleton className="h-4 w-40" />
                          <Skeleton className="h-4 w-28" />
                          <div className="flex gap-2 pt-1">
                            <Skeleton className="h-9 flex-1" />
                            <Skeleton className="h-9 w-28" />
                          </div>
                        </div>
                      ))
                    : filtered.map((branch) => (
                        <div
                          key={branch.id}
                          onClick={() => setActiveId(branch.id)}
                          className={cn(
                            "cursor-pointer rounded-xl border bg-card p-5 transition-all duration-200",
                            "hover:border-primary/30 hover:shadow-md",
                            activeBranch?.id === branch.id &&
                              "border-primary ring-1 ring-primary",
                            !branch.isOpen && "opacity-60",
                          )}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="font-serif text-lg font-semibold text-card-foreground">
                                  {branch.name}
                                </h3>
                                <Badge
                                  variant="secondary"
                                  className={cn(
                                    branch.isOpen
                                      ? "bg-green-100 text-green-700"
                                      : "bg-red-100 text-red-700",
                                  )}
                                >
                                  {branch.isOpen ? "Open" : "Closed"}
                                </Badge>
                              </div>

                              <div className="mt-3 space-y-2 text-sm text-muted-foreground">
                                <div className="flex items-center gap-2">
                                  <MapPin className="h-4 w-4 shrink-0" />
                                  <span>
                                    {branch.address}, {branch.city}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Clock className="h-4 w-4 shrink-0" />
                                  <span>{branch.hours}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Phone className="h-4 w-4 shrink-0" />
                                  <span>{branch.phone}</span>
                                </div>
                              </div>

                              {/* Features */}
                              <div className="mt-3 flex flex-wrap gap-1.5"></div>
                            </div>

                            <div className="flex flex-col items-end gap-2"></div>
                          </div>

                          <div className="mt-4 flex gap-2">
                            <Button
                              size="sm"
                              className="flex-1"
                              disabled={!branch.isOpen}
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate("/menu");
                              }}
                            >
                              Order from here
                            </Button>
                            <Button size="sm" variant="outline" asChild>
                              <a
                                href={directionsUrl(branch)}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <Navigation className="mr-1 h-4 w-4" />
                                Directions
                              </a>
                            </Button>
                          </div>
                        </div>
                      ))}
                  {!isLoading && filtered.length === 0 && (
                    <div className="rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground">
                      No locations match "{query}".
                    </div>
                  )}
                </div>
              </div>

              {/* Interactive Map */}
              <div className="lg:col-span-3">
                <div className="sticky top-24 space-y-3">
                  <div className="aspect-square overflow-hidden rounded-2xl border bg-muted lg:aspect-4/3">
                    {mapSrc ? (
                      <iframe
                        key={mapSrc}
                        title={`Map of ${activeBranch?.name ?? restaurantName}`}
                        src={mapSrc}
                        className="h-full w-full border-0"
                        loading="lazy"
                        referrerPolicy="no-referrer-when-downgrade"
                        allowFullScreen
                      />
                    ) : (
                      <div className="flex h-full flex-col items-center justify-center p-8 text-center">
                        <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-primary/10">
                          <MapPin className="h-10 w-10 text-primary" />
                        </div>
                        <p className="max-w-md text-muted-foreground">
                          {isLoading
                            ? "Loading locations…"
                            : `No ${restaurantName} locations to display yet.`}
                        </p>
                      </div>
                    )}
                  </div>
                  {activeBranch && (
                    <div className="flex flex-col gap-3 rounded-xl border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-card-foreground">
                          {activeBranch.name}
                        </p>
                        <p className="truncate text-sm text-muted-foreground">
                          {fullAddress(activeBranch)}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        className="shrink-0"
                        onClick={useMyLocation}
                        disabled={locating}
                      >
                        <LocateFixed className="mr-2 h-4 w-4" />
                        {locating
                          ? "Locating…"
                          : userLoc
                            ? "Location enabled"
                            : "Use my location"}
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
