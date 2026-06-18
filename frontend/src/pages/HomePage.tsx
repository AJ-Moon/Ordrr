import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { HeroSlider } from "@/components/home/hero-slider"
import { QuickActions } from "@/components/home/quick-actions"
import { MenuCategories } from "@/components/home/menu-categories"
import { FeaturedItems } from "@/components/home/featured-items"
import { DealsSection } from "@/components/home/deals-section"
import { AppPromo } from "@/components/home/app-promo"
import { ExperimentText } from "@/components/ExperimentText"
import { QuietHourBanner } from "@/components/QuietHourBanner"
import { PersonalizedMerchandising } from "@/components/PersonalizedMerchandising"

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <HeroSlider />
        <div className="border-b bg-muted/30 px-4 py-2 text-center text-sm text-muted-foreground">
          <ExperimentText placement="HOME_PROMO_COPY" fallback="Order fresh favorites online." />
        </div>
        <QuietHourBanner />
        <PersonalizedMerchandising />
        <QuickActions />
        <MenuCategories />
        <FeaturedItems />
        <DealsSection />
        <AppPromo />
      </main>
      <Footer />
    </div>
  )
}
