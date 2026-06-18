import { useEffect, useState } from "react"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Briefcase, MapPin, Coffee, GraduationCap, HeartPulse, Loader2 } from "lucide-react"
import { useRestaurant } from "@/contexts/RestaurantContext"

interface Benefit { icon?: string; title: string; desc: string }
interface Job { title: string; location: string; type: string; description: string }
interface CareersContent { benefits?: Benefit[]; jobs?: Job[] }

const ICON_MAP: Record<string, React.ElementType> = { HeartPulse, Coffee, GraduationCap, Briefcase }

const DEFAULT_BENEFITS: Benefit[] = [
  { icon: "HeartPulse", title: "Health & Wellness", desc: "Comprehensive medical, dental, and vision coverage." },
  { icon: "Coffee", title: "Free Meals", desc: "Enjoy our delicious food for free during your shifts." },
  { icon: "GraduationCap", title: "Career Growth", desc: "Ongoing training and clear paths for advancement." },
]

const DEFAULT_JOBS: Job[] = [
  { title: "Executive Chef", location: "Downtown Branch", type: "Full-time", description: "Lead our culinary team, design new seasonal menus, and ensure the highest quality of food preparation and presentation." },
  { title: "Restaurant Manager", location: "Westside Branch", type: "Full-time", description: "Oversee daily operations, manage staff, and guarantee an exceptional dining experience for every guest." },
  { title: "Line Cook", location: "Multiple Locations", type: "Full/Part-time", description: "Prepare ingredients and assemble dishes according to our recipes and stringent quality standards." },
  { title: "Front of House Staff", location: "Multiple Locations", type: "Full/Part-time", description: "Welcome guests, take orders, and provide attentive, friendly service throughout their dining experience." },
]

export default function CareersPage() {
  const { restaurantName } = useRestaurant()
  const [content, setContent] = useState<CareersContent>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch("/api/faqs/content/careers")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return
        let parsed: CareersContent = {}
        if (data.content) {
          try { parsed = JSON.parse(data.content) } catch { /* use defaults */ }
        }
        setContent(parsed)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const benefits = content.benefits?.length ? content.benefits : DEFAULT_BENEFITS
  const jobs = content.jobs?.length ? content.jobs : DEFAULT_JOBS

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="py-12 lg:py-20">
        <div className="mx-auto max-w-7xl px-4 lg:px-8">
          {/* Header */}
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h1 className="font-serif text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
              Join Our Team
            </h1>
            <p className="mt-4 text-lg text-muted-foreground">
              We&apos;re always looking for passionate, driven individuals to help us deliver extraordinary experiences. Build your career with {restaurantName}.
            </p>
          </div>

          {loading ? (
            <div className="flex justify-center py-24">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : (
            <>
              {/* Benefits */}
              <section className="mb-20">
                <h2 className="font-serif text-2xl font-bold text-center mb-10 text-foreground">Why Work With Us?</h2>
                <div className="grid sm:grid-cols-3 gap-8">
                  {benefits.map((benefit, idx) => {
                    const Icon = ICON_MAP[benefit.icon || ""] || HeartPulse
                    return (
                      <div key={idx} className="flex flex-col items-center text-center p-6 rounded-2xl bg-muted/50 border border-border/50">
                        <div className="h-14 w-14 rounded-full bg-secondary/20 flex items-center justify-center mb-4">
                          <Icon className="h-7 w-7 text-secondary" />
                        </div>
                        <h3 className="font-bold text-lg mb-2 text-foreground">{benefit.title}</h3>
                        <p className="text-muted-foreground text-sm">{benefit.desc}</p>
                      </div>
                    )
                  })}
                </div>
              </section>

              {/* Open Positions */}
              <section>
                <h2 className="font-serif text-2xl font-bold mb-8 text-foreground">Open Positions</h2>
                <div className="grid gap-6 md:grid-cols-2">
                  {jobs.map((job, idx) => (
                    <Card key={idx} className="flex flex-col h-full border-border hover:border-primary/30 transition-colors shadow-sm">
                      <CardHeader>
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <CardTitle className="text-xl font-bold">{job.title}</CardTitle>
                            <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                              <span className="flex items-center gap-1">
                                <MapPin className="h-4 w-4" /> {job.location}
                              </span>
                              <span className="flex items-center gap-1">
                                <Briefcase className="h-4 w-4" /> {job.type}
                              </span>
                            </div>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="flex-1 flex flex-col justify-between">
                        <p className="text-muted-foreground mb-6 text-sm leading-relaxed">
                          {job.description}
                        </p>
                        <Button className="w-full sm:w-auto self-start mt-auto">Apply Now</Button>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
      </main>
      <Footer />
    </div>
  )
}
