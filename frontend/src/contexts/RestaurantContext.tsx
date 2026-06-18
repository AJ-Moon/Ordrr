import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";

export interface RestaurantTheme {
  restaurantName: string;
  logoUrl: string;
  primaryColor: string;
  secondaryColor: string;
  deliveryCharge: number;
  minOrderAmount: number;
  restaurantOpen: string;
  cashOnDelivery: boolean;
  announcement: string;
  announcementActive: string;
  heroText: string;
  heroSubtext: string;
  slogan: string;
  heroImageUrl: string;
  layout: "classic" | "modern" | "minimal";
  fontFamily: string;
  slides: Array<{
    image: string;
    headline: string;
    subtext: string;
  }>;
  // Formerly hardcoded — now sourced from GET /api/settings
  currencySymbol: string;
  closedMessage: string;
  footerTagline: string;
  menuSubtitle: string;
  contactReplyTime: string;
  contactHoursNote: string;
  dealsSectionTitle: string;
  dealsSectionSubtitle: string;
  featuredSectionTitle: string;
  featuredSectionSubtitle: string;
  promoHeadline: string;
  promoBody: string;
  // Contact & social fields (from /api/settings)
  phone: string;
  email: string;
  address: string;
  instagramUrl: string;
  twitterUrl: string;
  tiktokUrl: string;
  whatsapp: string;
  mapsEmbed: string;
}

const DEFAULTS: RestaurantTheme = {
  restaurantName: "Restaurant",
  logoUrl: "",
  primaryColor: "#e85d04",
  secondaryColor: "#faa307",
  deliveryCharge: 0,
  minOrderAmount: 0,
  restaurantOpen: "true",
  cashOnDelivery: true,
  announcement: "",
  announcementActive: "false",
  heroText: "",
  heroSubtext: "",
  slogan: "",
  heroImageUrl: "",
  layout: "classic",
  fontFamily: "Inter",
  slides: [],
  currencySymbol: "$",
  closedMessage:
    "We're currently closed — You can still browse the menu and place orders for later.",
  footerTagline:
    "Fresh ingredients, bold flavors, and fast delivery. Experience the taste of perfection with every order.",
  menuSubtitle:
    "From flame-grilled burgers to wood-fired pizzas, explore flavors crafted with passion.",
  contactReplyTime: "We reply within 24 hours",
  contactHoursNote: "Daily, including holidays",
  dealsSectionTitle: "Deals You Won't Miss",
  dealsSectionSubtitle:
    "Grab these mouth-watering offers before they're gone. Handpicked combinations crafted just for you!",
  featuredSectionTitle: "Fan Favorites & New Arrivals",
  featuredSectionSubtitle:
    "Discover what everyone is ordering and try our latest creations",
  promoHeadline: "Order Online, Your Way",
  promoBody:
    "Browse our full menu, customize your order, and have it delivered or ready for pickup \u2014 no app required.",
  phone: "",
  email: "",
  address: "",
  instagramUrl: "",
  twitterUrl: "",
  tiktokUrl: "",
  whatsapp: "",
  mapsEmbed: "",
};

const THEME_CACHE_KEY = "restaurant_theme_cache";

function ThemeLoadingScreen() {
  return (
    <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-white">
      {/* Pulsing branded icon — uses a neutral gray until the real color loads */}
      <div className="relative mb-8 flex items-center justify-center">
        <span className="absolute h-28 w-28 animate-ping rounded-full bg-gray-300 opacity-20" />
        <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-gray-300 shadow-md">
          {/* Utensils icon */}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="white"
            className="h-10 w-10"
          >
            <path d="M11 9H9V2H7v7H5V2H3v7c0 2.12 1.66 3.84 3.75 3.97V22h2.5v-9.03C11.34 12.84 13 11.12 13 9V2h-2v7zm5-3v8h2.5v8H21V2c-2.76 0-5 2.24-5 4z" />
          </svg>
        </div>
      </div>

      {/* Bouncing dots */}
      <div className="flex items-center gap-1.5">
        {([0, 0.15, 0.3] as number[]).map((delay, i) => (
          <div
            key={i}
            className="h-2 w-2 animate-bounce rounded-full bg-gray-400"
            style={{ animationDelay: `${delay}s` }}
          />
        ))}
      </div>

      <p className="mt-5 text-sm tracking-wide text-gray-400">
        Loading your experience…
      </p>
    </div>
  );
}

const RestaurantContext = createContext<RestaurantTheme>(DEFAULTS);

export function RestaurantProvider({ children }: { children: ReactNode }) {
  // True immediately if we have a cached theme (returning user), false on cold start
  const [themeReady, setThemeReady] = useState(() => {
    try {
      return Boolean(localStorage.getItem(THEME_CACHE_KEY));
    } catch {
      return false;
    }
  });

  const [theme, setTheme] = useState<RestaurantTheme>(() => {
    try {
      const raw = localStorage.getItem(THEME_CACHE_KEY);
      if (!raw) return DEFAULTS;
      const cached = JSON.parse(raw) as Partial<RestaurantTheme>;
      return { ...DEFAULTS, ...cached };
    } catch {
      return DEFAULTS;
    }
  });

  useEffect(() => {
    Promise.all([
      fetch("/api/theme").then((r) => (r.ok ? r.json() : null)),
      fetch("/api/settings").then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([themeData, settingsData]) => {
        if (!themeData && !settingsData) return;
        const layout = themeData?.layout;
        setTheme({
          restaurantName:
            themeData?.restaurantName ||
            settingsData?.brand_name ||
            DEFAULTS.restaurantName,
          logoUrl: themeData?.logoUrl || "",
          primaryColor: themeData?.primaryColor || DEFAULTS.primaryColor,
          secondaryColor: themeData?.secondaryColor || DEFAULTS.secondaryColor,
          deliveryCharge: Math.max(
            0,
            Number.parseFloat(String(settingsData?.delivery_charge || "0")) ||
              0,
          ),
          minOrderAmount: Math.max(
            0,
            Number.parseFloat(String(settingsData?.min_order_amount || "0")) ||
              0,
          ),
          restaurantOpen:
            String(settingsData?.restaurant_open || "true").toLowerCase() ===
            "false"
              ? "false"
              : "true",
          cashOnDelivery:
            String(settingsData?.cash_on_delivery || "true").toLowerCase() ===
            "true",
          announcement: settingsData?.announcement || "",
          announcementActive:
            String(
              settingsData?.announcement_active || "false",
            ).toLowerCase() === "true"
              ? "true"
              : "false",
          heroText: themeData?.heroText || "",
          heroSubtext:
            themeData?.heroSubtext ||
            settingsData?.tagline ||
            DEFAULTS.heroSubtext,
          slogan:
            themeData?.slogan ||
            themeData?.heroSubtext ||
            settingsData?.tagline ||
            "",
          heroImageUrl: themeData?.heroImageUrl || "",
          layout:
            layout === "modern" || layout === "minimal" || layout === "classic"
              ? layout
              : "classic",
          fontFamily: themeData?.fontFamily || DEFAULTS.fontFamily,
          slides: Array.isArray(themeData?.slides)
            ? themeData.slides.slice(0, 3).map((slide: any) => ({
                image: String(slide?.image || ""),
                headline: String(slide?.headline || ""),
                subtext: String(slide?.subtext || ""),
              }))
            : [],
          // New fields from settings
          currencySymbol:
            settingsData?.currency_symbol || DEFAULTS.currencySymbol,
          closedMessage: settingsData?.closed_message || DEFAULTS.closedMessage,
          footerTagline: settingsData?.footer_tagline || DEFAULTS.footerTagline,
          menuSubtitle: settingsData?.menu_subtitle || DEFAULTS.menuSubtitle,
          contactReplyTime:
            settingsData?.contact_reply_time || DEFAULTS.contactReplyTime,
          contactHoursNote:
            settingsData?.contact_hours_note || DEFAULTS.contactHoursNote,
          dealsSectionTitle:
            settingsData?.deals_section_title || DEFAULTS.dealsSectionTitle,
          dealsSectionSubtitle:
            settingsData?.deals_section_subtitle ||
            DEFAULTS.dealsSectionSubtitle,
          featuredSectionTitle:
            settingsData?.featured_section_title ||
            DEFAULTS.featuredSectionTitle,
          featuredSectionSubtitle:
            settingsData?.featured_section_subtitle ||
            DEFAULTS.featuredSectionSubtitle,
          promoHeadline: settingsData?.promo_headline || DEFAULTS.promoHeadline,
          promoBody: settingsData?.promo_body || DEFAULTS.promoBody,
          // Contact & social
          phone: settingsData?.phone || "",
          email: settingsData?.email || "",
          address: settingsData?.address || "",
          instagramUrl: settingsData?.instagram_url || "",
          twitterUrl: settingsData?.twitter_url || "",
          tiktokUrl: settingsData?.tiktok_url || "",
          whatsapp: settingsData?.whatsapp || "",
          mapsEmbed: settingsData?.maps_embed || "",
        });
      })
      .catch(() => {})
      .finally(() => {
        setThemeReady(true);
        // Backend is now warm — kick off menu prefetch so homepage renders instantly
        fetch("/api/menu/").catch(() => {});
      });
  }, []);

  useEffect(() => {
    // Only cache small scalar fields — exclude large image URLs and slide arrays
    // which can easily blow the ~5 MB localStorage quota.
    const { slides, heroImageUrl, logoUrl, ...cacheable } = theme;
    try {
      localStorage.setItem(THEME_CACHE_KEY, JSON.stringify(cacheable));
    } catch {
      // Storage quota exceeded — clear the cache entry and continue without caching.
      try {
        localStorage.removeItem(THEME_CACHE_KEY);
      } catch {
        /* ignore */
      }
    }
  }, [theme]);

  useEffect(() => {
    document.documentElement.style.setProperty(
      "--brand-primary",
      theme.primaryColor,
    );
    document.documentElement.style.setProperty("--primary", theme.primaryColor);
    document.documentElement.style.setProperty("--ring", theme.primaryColor);
  }, [theme.primaryColor]);

  useEffect(() => {
    document.documentElement.style.setProperty(
      "--brand-secondary",
      theme.secondaryColor,
    );
    document.documentElement.style.setProperty(
      "--secondary",
      theme.secondaryColor,
    );
  }, [theme.secondaryColor]);

  if (!themeReady) return <ThemeLoadingScreen />;

  return (
    <RestaurantContext.Provider value={theme}>
      {children}
    </RestaurantContext.Provider>
  );
}

export function useRestaurant() {
  return useContext(RestaurantContext);
}

/** Fetch theme for a specific restaurant (used by admin panel). */
export async function fetchRestaurantTheme(
  restaurantId: number,
): Promise<RestaurantTheme> {
  try {
    const res = await fetch("/api/theme", {
      headers: { "X-Restaurant-ID": String(restaurantId) },
    });
    if (!res.ok) return DEFAULTS;
    const data = await res.json();
    return {
      restaurantName: data.restaurantName || DEFAULTS.restaurantName,
      logoUrl: data.logoUrl || "",
      primaryColor: data.primaryColor || DEFAULTS.primaryColor,
      secondaryColor: data.secondaryColor || DEFAULTS.secondaryColor,
      deliveryCharge: 0,
      minOrderAmount: 0,
      restaurantOpen: "true",
      cashOnDelivery: true,
      announcement: "",
      announcementActive: "false",
      heroText: data.heroText || "",
      heroSubtext: data.heroSubtext || "",
      slogan: data.slogan || data.heroSubtext || "",
      heroImageUrl: data.heroImageUrl || "",
      layout:
        data.layout === "modern" ||
        data.layout === "minimal" ||
        data.layout === "classic"
          ? data.layout
          : "classic",
      fontFamily: data.fontFamily || DEFAULTS.fontFamily,
      slides: Array.isArray(data?.slides)
        ? data.slides.slice(0, 3).map((slide: any) => ({
            image: String(slide?.image || ""),
            headline: String(slide?.headline || ""),
            subtext: String(slide?.subtext || ""),
          }))
        : [],
      currencySymbol: DEFAULTS.currencySymbol,
      closedMessage: DEFAULTS.closedMessage,
      footerTagline: DEFAULTS.footerTagline,
      menuSubtitle: DEFAULTS.menuSubtitle,
      contactReplyTime: DEFAULTS.contactReplyTime,
      contactHoursNote: DEFAULTS.contactHoursNote,
      dealsSectionTitle: DEFAULTS.dealsSectionTitle,
      dealsSectionSubtitle: DEFAULTS.dealsSectionSubtitle,
      featuredSectionTitle: DEFAULTS.featuredSectionTitle,
      featuredSectionSubtitle: DEFAULTS.featuredSectionSubtitle,
      promoHeadline: DEFAULTS.promoHeadline,
      promoBody: DEFAULTS.promoBody,
      phone: "",
      email: "",
      address: "",
      instagramUrl: "",
      twitterUrl: "",
      tiktokUrl: "",
      whatsapp: "",
      mapsEmbed: "",
    };
  } catch {
    return DEFAULTS;
  }
}
