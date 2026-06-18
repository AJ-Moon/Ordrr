import { useEffect, useState } from "react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { TrendingUp, Building, Users, Loader2 } from "lucide-react";
import { useRestaurant } from "@/contexts/RestaurantContext";

interface Feature {
  icon?: string;
  title: string;
  description: string;
}
interface FranchiseContent {
  intro_text?: string;
  features?: Feature[];
}

const ICON_MAP: Record<string, React.ElementType> = {
  TrendingUp,
  Building,
  Users,
};

const DEFAULT_INTRO =
  "Join one of the fastest-growing restaurant brands. We provide the recipe for success with comprehensive training, robust marketing support, and a proven operational model.";

const DEFAULT_FEATURES: Feature[] = [
  {
    icon: "TrendingUp",
    title: "Proven Profitability",
    description:
      "Our optimized supply chain and highly efficient kitchen layouts ensure great margins and strong ROI.",
  },
  {
    icon: "Building",
    title: "Store Design & Construction",
    description:
      "We assist with site selection, lease negotiation, and full turnkey restaurant build-outs.",
  },
  {
    icon: "Users",
    title: "Comprehensive Training",
    description:
      "Four weeks of intensive training for you and your management team at our corporate headquarters.",
  },
];

export default function FranchisePage() {
  const { restaurantName, phone } = useRestaurant() as any;
  const [content, setContent] = useState<FranchiseContent>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/faqs/content/franchise")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        let parsed: FranchiseContent = {};
        if (data.content) {
          try {
            parsed = JSON.parse(data.content);
          } catch {
            /* use defaults */
          }
        }
        setContent(parsed);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const introText = content.intro_text || DEFAULT_INTRO;
  const features = content.features?.length
    ? content.features
    : DEFAULT_FEATURES;

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="py-12 lg:py-20">
        <div className="mx-auto max-w-7xl px-4 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-20 items-start">
            {/* Left Content */}
            <div>
              <h1 className="font-serif text-4xl font-bold tracking-tight text-foreground sm:text-5xl mb-6">
                Own a {restaurantName}
              </h1>
              {loading ? (
                <div className="flex items-center gap-2 text-muted-foreground mb-10">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Loading…</span>
                </div>
              ) : (
                <p className="text-lg text-muted-foreground mb-10 leading-relaxed">
                  {introText}
                </p>
              )}

              <div className="space-y-8">
                {features.map((feature, idx) => {
                  const Icon = ICON_MAP[feature.icon || ""] || TrendingUp;
                  return (
                    <div key={idx} className="flex gap-4">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                        <Icon className="h-6 w-6 text-primary" />
                      </div>
                      <div>
                        <h3 className="font-bold text-xl text-foreground mb-2">
                          {feature.title}
                        </h3>
                        <p className="text-muted-foreground">
                          {feature.description}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right Form */}
            <div className="bg-card p-6 sm:p-10 rounded-3xl shadow-lg border border-border">
              <h2 className="font-serif text-2xl font-bold text-foreground mb-2">
                Request Information
              </h2>
              <p className="text-muted-foreground text-sm mb-8">
                Fill out the form below and our franchise development team will
                contact you shortly.
              </p>

              <form className="space-y-5" onSubmit={(e) => e.preventDefault()}>
                <div className="grid sm:grid-cols-2 gap-5">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">First Name</label>
                    <Input placeholder="John" className="bg-background" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Last Name</label>
                    <Input placeholder="Doe" className="bg-background" />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Email Address</label>
                  <Input
                    type="email"
                    placeholder="john@example.com"
                    className="bg-background"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Phone Number</label>
                  <Input
                    type="tel"
                    placeholder={phone || "(555) 123-4567"}
                    className="bg-background"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    Available Liquid Capital
                  </label>
                  <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
                    <option value="">Select an amount</option>
                    <option value="100k">$100,000 - $250,000</option>
                    <option value="250k">$250,000 - $500,000</option>
                    <option value="500k">$500,000+</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    Interested Locations / Message
                  </label>
                  <Textarea
                    placeholder={`Tell us where you want to open a ${restaurantName}...`}
                    className="bg-background resize-none h-24"
                  />
                </div>

                <Button className="w-full h-12 text-base font-semibold mt-4">
                  Submit Inquiry
                </Button>
                <p className="text-xs text-center text-muted-foreground mt-4">
                  By submitting, you agree to our Privacy Policy and Terms of
                  Service.
                </p>
              </form>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
