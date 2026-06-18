import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRestaurant } from "@/contexts/RestaurantContext";

const DEFAULT_SLIDE = {
  headline: "Fresh. Fast. Delicious.",
  subheadline:
    "Taste the difference with our handcrafted recipes made from the freshest ingredients.",
  image: "/images/hero-burger.jpg",
};

export function HeroSlider() {
  const {
    restaurantName,
    slogan,
    heroSubtext,
    heroImageUrl,
    primaryColor,
    layout,
    slides,
  } = useRestaurant();
  const [current, setCurrent] = useState(0);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);
  const effectiveSlogan = slogan || heroSubtext;

  const configuredSlides = slides
    .filter((slide) => slide.image || slide.headline || slide.subtext)
    .slice(0, 3)
    .map((slide, index) => ({
      id: index + 1,
      headline: slide.headline.trim() || DEFAULT_SLIDE.headline,
      subheadline: slide.subtext.trim() || DEFAULT_SLIDE.subheadline,
      image: slide.image.trim() || DEFAULT_SLIDE.image,
    }));

  const sliderSlides =
    configuredSlides.length > 0
      ? configuredSlides
      : [
          {
            id: 1,
            headline: DEFAULT_SLIDE.headline,
            subheadline: DEFAULT_SLIDE.subheadline,
            image: heroImageUrl || DEFAULT_SLIDE.image,
          },
        ];

  const showSliderControls = sliderSlides.length > 1 && layout !== "minimal";

  const nextSlide = useCallback(() => {
    setCurrent((prev) => (prev + 1) % sliderSlides.length);
  }, [sliderSlides.length]);

  useEffect(() => {
    if (!isAutoPlaying || layout === "minimal" || sliderSlides.length <= 1) {
      return;
    }
    const interval = setInterval(nextSlide, 3000);
    return () => clearInterval(interval);
  }, [isAutoPlaying, nextSlide, layout, sliderSlides.length]);

  useEffect(() => {
    if (current >= sliderSlides.length) {
      setCurrent(0);
    }
  }, [current, sliderSlides.length]);

  if (layout === "minimal") {
    return (
      <section className="border-b bg-background">
        <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-14 lg:px-8 lg:py-16">
          <p
            className="text-sm font-semibold uppercase tracking-[0.2em]"
            style={{ color: primaryColor }}
          >
            Welcome
          </p>
          <h1 className="mt-3 max-w-3xl font-serif text-3xl font-bold leading-tight text-foreground sm:text-4xl lg:text-5xl">
            {restaurantName}
          </h1>
          <p className="mt-4 max-w-2xl text-base text-muted-foreground sm:text-lg">
            {effectiveSlogan ||
              "Discover handcrafted meals made with fresh ingredients every day."}
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button size="lg" style={{ backgroundColor: primaryColor }} asChild>
              <Link to="/menu">Order Now</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link to="/menu">Explore Menu</Link>
            </Button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section
      className={cn(
        "relative w-full overflow-hidden",
        layout === "modern"
          ? "h-[420px] sm:h-[560px] lg:h-[680px]"
          : "h-[380px] sm:h-[500px] lg:h-[620px]",
      )}
      onMouseEnter={() => setIsAutoPlaying(false)}
      onMouseLeave={() => setIsAutoPlaying(true)}
    >
      {/* Slides */}
      {sliderSlides.map((slide, index) => (
        <div
          key={slide.id}
          className={cn(
            "absolute inset-0 transition-opacity duration-700",
            index === current ? "opacity-100" : "pointer-events-none opacity-0",
          )}
        >
          {/* Background Image */}
          <div
            className="absolute inset-0 bg-cover bg-center"
            style={{ backgroundImage: `url(${slide.image})` }}
          >
            {/* Gradient Overlay */}
            <div
              className="absolute inset-0"
              style={{
                background:
                  layout === "modern"
                    ? `linear-gradient(100deg, ${primaryColor}D9 0%, ${primaryColor}7A 42%, rgba(0,0,0,0.15) 100%)`
                    : `linear-gradient(90deg, ${primaryColor}C7 0%, rgba(0,0,0,0.35) 60%, rgba(0,0,0,0.2) 100%)`,
              }}
            />
          </div>

          {/* Content */}
          <div className="relative z-10 mx-auto flex h-full max-w-7xl items-center px-4 sm:px-6 lg:px-8">
            <div className="max-w-2xl">
              <h1
                className={cn(
                  "font-serif text-3xl font-bold leading-tight tracking-tight text-white sm:text-5xl lg:text-6xl",
                  "transform transition-all delay-100 duration-700",
                  index === current
                    ? "translate-y-0 opacity-100"
                    : "translate-y-8 opacity-0",
                )}
              >
                {slide.headline}
              </h1>
              <p
                className={cn(
                  "mt-3 text-base leading-relaxed text-white/90 sm:mt-4 sm:text-xl",
                  "transform transition-all delay-200 duration-700",
                  index === current
                    ? "translate-y-0 opacity-100"
                    : "translate-y-8 opacity-0",
                )}
              >
                {slide.subheadline}
              </p>

              <div className="mt-5 flex flex-wrap gap-3 leading-none sm:mt-8 sm:gap-4">
                <Button
                  size="lg"
                  className="h-11 px-6 text-sm font-semibold sm:h-12 sm:px-8 sm:text-base"
                  style={{ backgroundColor: primaryColor }}
                  asChild
                >
                  <Link to="/menu">Order Now</Link>
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  className="h-11 border-white/35 bg-white/10 px-6 text-sm font-semibold text-white backdrop-blur-sm hover:bg-white/20 hover:text-white sm:h-12 sm:px-8 sm:text-base"
                  asChild
                >
                  <Link to="/menu">Explore Menu</Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      ))}

      {/* Scroll Down Indicator */}
      <div className="absolute bottom-1 left-1/2 z-20 flex -translate-x-1/2 flex-col items-center gap-1 sm:bottom-2">
        <span className="text-xs font-medium uppercase tracking-widest text-white/70">
          Scroll for menu
        </span>
        <ChevronDown className="h-5 w-5 animate-bounce text-white/70" />
      </div>

      {/* Slide Indicators */}
      {showSliderControls && (
        <div className="absolute bottom-5 left-1/2 z-20 flex -translate-x-1/2 gap-2 sm:bottom-6">
          {sliderSlides.map((_, index) => (
            <button
              key={index}
              onClick={() => setCurrent(index)}
              className={cn(
                "h-2 rounded-full transition-all duration-300",
                index === current ? "w-8" : "w-2 bg-white/50 hover:bg-white/70",
              )}
              style={
                index === current
                  ? { backgroundColor: primaryColor }
                  : undefined
              }
              aria-label={`Go to slide ${index + 1}`}
            />
          ))}
        </div>
      )}
    </section>
  );
}
