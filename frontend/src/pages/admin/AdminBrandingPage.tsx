import { useEffect, useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Info,
  Loader2,
  Paintbrush,
  Plus,
  Save,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type LayoutOption = "classic" | "modern" | "minimal";

interface HeroSlide {
  image: string;
  headline: string;
  subtext: string;
}

interface BrandingForm {
  layout: LayoutOption;
  primaryColor: string;
  restaurantName: string;
  slogan: string;
  logoUrl: string;
  heroImageUrl: string;
  slides: HeroSlide[];
}

const DEFAULTS: BrandingForm = {
  layout: "classic",
  primaryColor: "#e85d04",
  restaurantName: "My Restaurant",
  slogan: "",
  logoUrl: "",
  heroImageUrl: "",
  slides: [],
};

const COLOR_PRESETS = [
  "#dc2626",
  "#f97316",
  "#16a34a",
  "#2563eb",
  "#7c3aed",
  "#e11d48",
  "#d97706",
  "#0d9488",
];

const HEX_RE = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;

function adminFetch(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem("admin_token");
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
}

async function uploadAdminImage(file: File): Promise<string> {
  const token = localStorage.getItem("admin_token");
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch("/api/admin/upload-image", {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (!res.ok) {
    throw new Error("Upload failed");
  }

  const data = (await res.json()) as { url?: string };
  if (!data.url) {
    throw new Error("Missing image URL");
  }
  return data.url;
}

async function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

function LayoutMockup({ layout }: { layout: LayoutOption }) {
  if (layout === "classic") {
    return (
      <div className="h-28 w-full rounded-lg border bg-muted/30 p-3">
        <div className="h-8 rounded bg-muted" />
        <div className="mt-3 flex gap-2">
          <div className="h-4 w-16 rounded-full bg-muted" />
          <div className="h-4 w-14 rounded-full bg-muted" />
          <div className="h-4 w-20 rounded-full bg-muted" />
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <div className="h-8 rounded bg-muted" />
          <div className="h-8 rounded bg-muted" />
          <div className="h-8 rounded bg-muted" />
        </div>
      </div>
    );
  }

  if (layout === "modern") {
    return (
      <div className="h-28 w-full rounded-lg border bg-muted/30 p-3">
        <div className="relative h-10 rounded bg-muted">
          <div className="absolute left-2 top-2 h-2 w-24 rounded bg-background/80" />
          <div className="absolute left-2 top-5 h-2 w-16 rounded bg-background/60" />
        </div>
        <div className="mt-3 flex gap-2 overflow-hidden">
          <div className="h-4 w-14 rounded-full bg-muted" />
          <div className="h-4 w-14 rounded-full bg-muted" />
          <div className="h-4 w-14 rounded-full bg-muted" />
          <div className="h-4 w-14 rounded-full bg-muted" />
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="h-6 rounded bg-muted" />
          <div className="h-6 rounded bg-muted" />
        </div>
      </div>
    );
  }

  return (
    <div className="h-28 w-full rounded-lg border bg-muted/30 p-3">
      <div className="h-2 w-20 rounded bg-muted" />
      <div className="mt-2 h-1.5 w-36 rounded bg-muted" />
      <div className="mt-4 space-y-2">
        <div className="h-5 rounded border bg-background/90" />
        <div className="h-5 rounded border bg-background/90" />
        <div className="h-5 rounded border bg-background/90" />
      </div>
    </div>
  );
}

const layoutOptions: Array<{
  id: LayoutOption;
  name: string;
  description: string;
}> = [
  {
    id: "classic",
    name: "Classic",
    description:
      "Hero image on top, menu categories below, and a grid of items.",
  },
  {
    id: "modern",
    name: "Modern",
    description:
      "Full-width hero with overlay text, horizontal categories, card menu.",
  },
  {
    id: "minimal",
    name: "Minimal",
    description:
      "No hero image, list-style menu, typography-first presentation.",
  },
];

export default function AdminBrandingPage() {
  const [form, setForm] = useState<BrandingForm>(DEFAULTS);
  const [showGuide, setShowGuide] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingSlideIndex, setUploadingSlideIndex] = useState<number | null>(
    null,
  );

  useEffect(() => {
    const dismissed =
      localStorage.getItem("admin_branding_guide_dismissed") === "true";
    if (dismissed) setShowGuide(false);
  }, []);

  useEffect(() => {
    adminFetch("/api/admin/branding")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        setForm({
          layout: (data.layout as LayoutOption) || DEFAULTS.layout,
          primaryColor: data.primaryColor || DEFAULTS.primaryColor,
          restaurantName: data.restaurantName || DEFAULTS.restaurantName,
          slogan: data.slogan || "",
          logoUrl: data.logoUrl || "",
          heroImageUrl: data.heroImageUrl || "",
          slides: Array.isArray(data.slides)
            ? data.slides.slice(0, 3).map((slide: Partial<HeroSlide>) => ({
                image: String(slide?.image || ""),
                headline: String(slide?.headline || ""),
                subtext: String(slide?.subtext || ""),
              }))
            : [],
        });
      })
      .catch(() => {
        toast.error("Could not load branding settings");
      })
      .finally(() => setLoading(false));
  }, []);

  const setField = <K extends keyof BrandingForm>(
    key: K,
    value: BrandingForm[K],
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const onCustomHexChange = (value: string) => {
    setField("primaryColor", value);
  };

  const onLogoUpload = async (file?: File) => {
    if (!file) return;
    try {
      const data = await fileToDataUrl(file);
      setField("logoUrl", data);
    } catch {
      toast.error("Failed to load logo image");
    }
  };

  const onHeroUpload = async (file?: File) => {
    if (!file) return;
    try {
      const data = await fileToDataUrl(file);
      setField("heroImageUrl", data);
    } catch {
      toast.error("Failed to load hero image");
    }
  };

  const addSlide = () => {
    setForm((prev) => {
      if (prev.slides.length >= 3) return prev;
      return {
        ...prev,
        slides: [...prev.slides, { image: "", headline: "", subtext: "" }],
      };
    });
  };

  const removeSlide = (index: number) => {
    setForm((prev) => ({
      ...prev,
      slides: prev.slides.filter((_, i) => i !== index),
    }));
  };

  const moveSlide = (index: number, direction: -1 | 1) => {
    setForm((prev) => {
      const target = index + direction;
      if (target < 0 || target >= prev.slides.length) return prev;
      const next = [...prev.slides];
      [next[index], next[target]] = [next[target], next[index]];
      return { ...prev, slides: next };
    });
  };

  const setSlideField = <K extends keyof HeroSlide>(
    index: number,
    key: K,
    value: HeroSlide[K],
  ) => {
    setForm((prev) => ({
      ...prev,
      slides: prev.slides.map((slide, i) =>
        i === index ? { ...slide, [key]: value } : slide,
      ),
    }));
  };

  const onSlideImageUpload = async (index: number, file?: File) => {
    if (!file) return;
    setUploadingSlideIndex(index);
    try {
      const url = await uploadAdminImage(file);
      setSlideField(index, "image", url);
      toast.success("Slide image uploaded");
    } catch {
      toast.error("Failed to upload slide image");
    } finally {
      setUploadingSlideIndex(null);
    }
  };

  const save = async () => {
    const color = form.primaryColor.trim();
    if (!HEX_RE.test(color)) {
      toast.error("Primary color must be a valid hex value like #e85d04");
      return;
    }

    setSaving(true);
    try {
      const res = await adminFetch("/api/admin/branding", {
        method: "PATCH",
        body: JSON.stringify({
          layout: form.layout,
          primaryColor: color,
          restaurantName: form.restaurantName.trim(),
          slogan: form.slogan.trim(),
          logoUrl: form.logoUrl,
          heroImageUrl: form.heroImageUrl,
          slides: form.slides
            .map((slide) => ({
              image: slide.image.trim(),
              headline: slide.headline.trim(),
              subtext: slide.subtext.trim(),
            }))
            .filter((slide) => slide.image || slide.headline || slide.subtext),
        }),
      });
      if (!res.ok) throw new Error("save failed");
      // Apply color to the page immediately — no need to reload
      document.documentElement.style.setProperty("--brand-primary", color);
      document.documentElement.style.setProperty("--primary", color);
      document.documentElement.style.setProperty("--ring", color);
      // Clear the theme cache so the next customer page load fetches fresh data
      try { localStorage.removeItem("restaurant_theme_cache"); } catch { /* ignore */ }
      toast.success("Branding saved successfully");
    } catch {
      toast.error("Failed to save branding settings");
    } finally {
      setSaving(false);
    }
  };

  const previewBackground = useMemo(() => {
    if (form.layout === "minimal" || !form.heroImageUrl) return undefined;
    return {
      backgroundImage: `linear-gradient(120deg, ${form.primaryColor}CC, ${form.primaryColor}55), url(${form.heroImageUrl})`,
      backgroundSize: "cover",
      backgroundPosition: "center",
    } as const;
  }, [form.heroImageUrl, form.layout, form.primaryColor]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-8 pb-28 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Branding & Appearance</h1>
          <p className="text-sm text-muted-foreground">
            Customize how your customer-facing website looks.
          </p>
        </div>
        {!showGuide && (
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              localStorage.removeItem("admin_branding_guide_dismissed");
              setShowGuide(true);
            }}
          >
            Show Setup Guide
          </Button>
        )}
      </div>

      {showGuide && (
        <div className="rounded-xl border bg-muted/30 p-4">
          <div className="mb-3 flex items-start justify-between gap-4">
            <div className="flex items-start gap-2">
              <Info className="mt-0.5 h-4 w-4 text-primary" />
              <div>
                <h2 className="text-sm font-semibold">Branding Setup Guide</h2>
                <p className="text-xs text-muted-foreground">
                  Follow these steps to keep your storefront look consistent and
                  professional.
                </p>
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                localStorage.setItem("admin_branding_guide_dismissed", "true");
                setShowGuide(false);
              }}
            >
              Dismiss
            </Button>
          </div>
          <ol className="ml-5 list-decimal space-y-1 text-sm text-foreground">
            <li>
              Choose a layout first so all preview decisions match the final
              structure.
            </li>
            <li>
              Pick your primary brand color and confirm the button/text preview.
            </li>
            <li>Set restaurant name, slogan, logo, and hero image.</li>
            <li>
              Add up to 3 hero slides with clear headline and subtext for
              promotions.
            </li>
            <li>
              Reorder slides so the most important message appears first, then
              save.
            </li>
          </ol>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Layout Picker</CardTitle>
          <CardDescription>
            Choose one layout style for your storefront.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          {layoutOptions.map((opt) => {
            const selected = form.layout === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => setField("layout", opt.id)}
                className={cn(
                  "rounded-xl border p-3 text-left transition-all",
                  "hover:border-primary/60 hover:bg-muted/40",
                  selected && "border-primary ring-2 ring-primary/20",
                )}
              >
                <div className="mb-3 relative">
                  <LayoutMockup layout={opt.id} />
                  {selected && (
                    <CheckCircle2 className="absolute right-2 top-2 h-5 w-5 text-primary" />
                  )}
                </div>
                <p className="font-semibold">{opt.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {opt.description}
                </p>
              </button>
            );
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Color Scheme</CardTitle>
          <CardDescription>
            Primary color controls buttons, highlights, and accents on your
            website.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label>Preset Colors</Label>
            <div className="flex flex-wrap gap-2">
              {COLOR_PRESETS.map((c) => {
                const active =
                  form.primaryColor.toLowerCase() === c.toLowerCase();
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setField("primaryColor", c)}
                    className={cn(
                      "h-9 w-9 rounded-full border-2 transition-transform hover:scale-105",
                      active ? "border-foreground" : "border-transparent",
                    )}
                    style={{ backgroundColor: c }}
                    title={c}
                  />
                );
              })}
            </div>
          </div>

          <div className="max-w-xs space-y-2">
            <Label htmlFor="custom-hex">Custom Hex Color</Label>
            <Input
              id="custom-hex"
              value={form.primaryColor}
              onChange={(e) => onCustomHexChange(e.target.value)}
              placeholder="#e85d04"
            />
            {form.primaryColor && !HEX_RE.test(form.primaryColor) && (
              <p className="text-xs text-destructive">
                Enter a valid hex color (e.g. #1d4ed8).
              </p>
            )}
          </div>

          <div className="rounded-lg border p-4">
            <p className="mb-3 text-sm font-medium">Live color preview</p>
            <h3
              className="text-lg font-semibold"
              style={{ color: form.primaryColor }}
            >
              Signature Meals
            </h3>
            <Button
              className="mt-3"
              style={{ backgroundColor: form.primaryColor }}
            >
              Order Now
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Brand Details</CardTitle>
          <CardDescription>
            Update your restaurant identity and hero media.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="restaurant-name">Restaurant name</Label>
              <Input
                id="restaurant-name"
                value={form.restaurantName}
                onChange={(e) => setField("restaurantName", e.target.value)}
                placeholder="Flavor Hub"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="slogan">Slogan / Tagline</Label>
              <Input
                id="slogan"
                value={form.slogan}
                maxLength={80}
                onChange={(e) => setField("slogan", e.target.value)}
                placeholder="Fresh flavors delivered fast"
              />
              <p className="text-xs text-muted-foreground">
                {form.slogan.length}/80
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="logo-upload">Logo upload</Label>
              <Input
                id="logo-upload"
                type="file"
                accept="image/*"
                onChange={(e) => onLogoUpload(e.target.files?.[0])}
              />
              {form.logoUrl && (
                <div className="w-24 h-24 rounded-lg border bg-muted/20 p-2 flex items-center justify-center">
                  <img
                    src={form.logoUrl}
                    alt="Logo preview"
                    className="max-h-full max-w-full object-contain"
                  />
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="hero-upload">Hero image upload</Label>
              <Input
                id="hero-upload"
                type="file"
                accept="image/*"
                onChange={(e) => onHeroUpload(e.target.files?.[0])}
              />
              {form.heroImageUrl && (
                <div className="overflow-hidden rounded-lg border">
                  <img
                    src={form.heroImageUrl}
                    alt="Hero preview"
                    className="h-32 w-full object-cover"
                  />
                </div>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <Label>Preview Banner</Label>
            <div
              className={cn(
                "relative rounded-xl border min-h-[250px] overflow-hidden",
                form.layout === "minimal" && "bg-background",
              )}
              style={previewBackground}
            >
              {!previewBackground && form.layout !== "minimal" && (
                <div
                  className="absolute inset-0"
                  style={{
                    background: `linear-gradient(130deg, ${form.primaryColor}DD, ${form.primaryColor}44)`,
                  }}
                />
              )}

              <div
                className={cn(
                  "relative z-10 p-6",
                  form.layout === "minimal" ? "text-foreground" : "text-white",
                )}
              >
                <div className="mb-5 flex items-center gap-3">
                  {form.logoUrl ? (
                    <img
                      src={form.logoUrl}
                      alt="Brand logo"
                      className="h-12 w-12 rounded-md bg-white object-contain p-1"
                    />
                  ) : (
                    <div className="h-12 w-12 rounded-md bg-white/80 flex items-center justify-center">
                      <Paintbrush className="h-5 w-5 text-muted-foreground" />
                    </div>
                  )}
                  <div>
                    <p className="text-xl font-semibold">
                      {form.restaurantName.trim() || "Your Restaurant Name"}
                    </p>
                    <p
                      className={cn(
                        "text-sm",
                        form.layout === "minimal"
                          ? "text-muted-foreground"
                          : "text-white/90",
                      )}
                    >
                      {form.slogan.trim() || "Your tagline will appear here."}
                    </p>
                  </div>
                </div>

                <Button style={{ backgroundColor: form.primaryColor }}>
                  Explore Menu
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Hero Slides</CardTitle>
          <CardDescription>
            Manage up to 3 homepage hero slides. Reorder slides with arrows.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {form.slides.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No hero slides yet. Add one to get started.
            </p>
          )}

          {form.slides.map((slide, index) => (
            <div
              key={`${index}-${slide.image}`}
              className="rounded-lg border p-4 space-y-3"
            >
              <div className="flex items-center justify-between">
                <Label>Slide {index + 1}</Label>
                <div className="flex items-center gap-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    disabled={index === 0}
                    onClick={() => moveSlide(index, -1)}
                  >
                    <ArrowUp className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    disabled={index === form.slides.length - 1}
                    onClick={() => moveSlide(index, 1)}
                  >
                    <ArrowDown className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive hover:text-destructive"
                    onClick={() => removeSlide(index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Slide image</Label>
                <Input
                  type="file"
                  accept="image/*"
                  onChange={(e) =>
                    onSlideImageUpload(index, e.target.files?.[0])
                  }
                />
                {uploadingSlideIndex === index && (
                  <p className="text-xs text-muted-foreground">
                    Uploading image...
                  </p>
                )}
                {slide.image && (
                  <div className="overflow-hidden rounded-lg border">
                    <img
                      src={slide.image}
                      alt={`Slide ${index + 1}`}
                      className="h-28 w-full object-cover"
                    />
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label>Headline</Label>
                <Input
                  value={slide.headline}
                  onChange={(e) =>
                    setSlideField(index, "headline", e.target.value)
                  }
                  placeholder="Fresh. Fast. Delicious."
                />
              </div>

              <div className="space-y-2">
                <Label>Subtext</Label>
                <Input
                  value={slide.subtext}
                  onChange={(e) =>
                    setSlideField(index, "subtext", e.target.value)
                  }
                  placeholder="Tell customers what makes this slide special"
                />
              </div>
            </div>
          ))}

          <Button
            type="button"
            variant="outline"
            onClick={addSlide}
            disabled={form.slides.length >= 3}
          >
            <Plus className="mr-2 h-4 w-4" />
            Add Slide
          </Button>

          <div className="space-y-2 pt-2">
            <Label>Live preview strip</Label>
            <div className="grid gap-3 md:grid-cols-3">
              {Array.from({ length: 3 }).map((_, index) => {
                const slide = form.slides[index];
                return (
                  <div
                    key={index}
                    className="overflow-hidden rounded-lg border bg-muted/10"
                  >
                    <div className="relative h-24 w-full bg-muted/30">
                      {slide?.image ? (
                        <img
                          src={slide.image}
                          alt={`Preview slide ${index + 1}`}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                          Empty slot
                        </div>
                      )}
                    </div>
                    <div className="space-y-1 p-2">
                      <p className="line-clamp-1 text-xs font-semibold text-foreground">
                        {slide?.headline || `Slide ${index + 1}`}
                      </p>
                      <p className="line-clamp-2 text-[11px] text-muted-foreground">
                        {slide?.subtext || "No subtext"}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="fixed bottom-0 left-64 right-0 z-20 border-t bg-background/95 backdrop-blur p-4">
        <div className="flex items-center justify-end">
          <Button onClick={save} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save Branding
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
