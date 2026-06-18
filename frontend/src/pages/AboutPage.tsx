import { useEffect, useState } from "react"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { Target, Heart, Award, Users } from "lucide-react"
import { useRestaurant } from "@/contexts/RestaurantContext"

interface AboutValue {
  icon?: string
  title: string
  description: string
}

interface AboutContent {
  tagline?: string
  hero_image?: string
  kitchen_image?: string
  story_paragraph_1?: string
  story_paragraph_2?: string
  values?: AboutValue[]
}

const ICON_MAP: Record<string, React.ElementType> = {
  Heart, Target, Users, Award,
}

const DEFAULT_VALUES: AboutValue[] = [
  { icon: "Heart", title: "Passion for Food", description: "We pour our love into every recipe, ensuring each bite is memorable." },
  { icon: "Target", title: "Quality First", description: "Only the freshest, locally sourced ingredients make it to our kitchen." },
  { icon: "Users", title: "Community Focused", description: "We believe in giving back and creating a welcoming space for everyone." },
  { icon: "Award", title: "Excellence", description: "We strive for perfection in our service, atmosphere, and culinary creations." },
]

export default function AboutPage() {
  const { restaurantName } = useRestaurant()
  const [content, setContent] = useState<AboutContent>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch("/api/faqs/content/about")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return
        // Content may be stored as a JSON string inside the `content` field
        let parsed: AboutContent = {}
        if (data.content) {
          try { parsed = JSON.parse(data.content) } catch { /* plain text fallback */ }
        }
        setContent(parsed)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const tagline = content.tagline || `Bringing people together over exceptional food.`
  const heroImage = content.hero_image || "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1200&q=80"
  const kitchenImage = content.kitchen_image || "https://images.unsplash.com/photo-1556155092-490a1ba16284?w=800&q=80"
  const para1 = content.story_paragraph_1 || `${restaurantName} started with a simple belief: great food has the power to connect people. What began as a small family kitchen has blossomed into a beloved local destination for culinary comfort and innovation.`
  const para2 = content.story_paragraph_2 || `Our chefs work tirelessly to blend classic comfort flavors with modern twists. Every dish is a testament to our dedication to quality, sustainability, and authentic hospitality.`
  const values = content.values?.length ? content.values : DEFAULT_VALUES

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        {/* Hero Section */}
        <section className="relative h-[400px] w-full lg:h-[500px]">
          <img
            src={heroImage}
            alt={`${restaurantName} Restaurant Interior`}
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-black/60" />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center px-4">
              <h1 className="font-serif text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-7xl">
                Our Story
              </h1>
              {!loading && (
                <p className="mt-4 text-lg text-white/90 sm:text-xl max-w-2xl mx-auto">
                  {tagline}
                </p>
              )}
            </div>
          </div>
        </section>

        {/* Mission Section */}
        <section className="py-16 lg:py-24">
          <div className="mx-auto max-w-7xl px-4 lg:px-8">
            <div className="grid gap-12 lg:grid-cols-2 lg:gap-16 items-center">
              <div>
                <h2 className="font-serif text-3xl font-bold text-foreground sm:text-4xl">
                  More Than Just a Meal
                </h2>
                {loading ? (
                  <div className="mt-6 space-y-3">
                    <div className="h-4 w-full animate-pulse rounded bg-muted" />
                    <div className="h-4 w-5/6 animate-pulse rounded bg-muted" />
                    <div className="h-4 w-4/5 animate-pulse rounded bg-muted" />
                  </div>
                ) : (
                  <div className="mt-6 space-y-6 text-lg text-muted-foreground">
                    <p>{para1}</p>
                    <p>{para2}</p>
                  </div>
                )}
              </div>
              <div className="relative aspect-4/3 rounded-2xl overflow-hidden shadow-2xl">
                <img
                  src={kitchenImage}
                  alt="Chefs cooking in the kitchen"
                  className="absolute inset-0 h-full w-full object-cover"
                />
              </div>
            </div>
          </div>
        </section>

        {/* Values Section */}
        <section className="bg-muted py-16 lg:py-24">
          <div className="mx-auto max-w-7xl px-4 lg:px-8">
            <div className="text-center mb-16">
              <h2 className="font-serif text-3xl font-bold text-foreground sm:text-4xl">Our Core Values</h2>
              <p className="mt-4 text-muted-foreground text-lg">The principles that guide everything we do.</p>
            </div>
            {loading ? (
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="bg-card p-6 rounded-2xl border border-border">
                    <div className="mx-auto mb-6 h-16 w-16 animate-pulse rounded-full bg-muted" />
                    <div className="h-5 w-2/3 mx-auto mb-3 animate-pulse rounded bg-muted" />
                    <div className="h-3 w-full animate-pulse rounded bg-muted" />
                  </div>
                ))}
              </div>
            ) : (
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
                {values.map((value, idx) => {
                  const Icon = ICON_MAP[value.icon || ""] || Heart
                  return (
                    <div key={idx} className="bg-card p-6 rounded-2xl shadow-sm border border-border text-center">
                      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 mb-6">
                        <Icon className="h-8 w-8 text-primary" />
                      </div>
                      <h3 className="font-serif text-xl font-bold text-foreground mb-3">{value.title}</h3>
                      <p className="text-muted-foreground leading-relaxed">{value.description}</p>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </section>
      </main>
      <Footer />
    </div>
  )
}
