import { useEffect, useState } from "react"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { ChevronDown, MessageCircleQuestion } from "lucide-react"

interface Faq { id: number; question: string; answer: string; category: string; orderIndex: number }

export default function FaqPage() {
  const [faqs, setFaqs] = useState<Faq[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch("/api/faqs/")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (Array.isArray(data) && data.length) {
          setFaqs(data)
        }
        // If API returns empty or null we simply leave faqs = [] — no misleading fallback data.
      })
      .catch(() => { /* leave faqs empty */ })
      .finally(() => setLoading(false))
  }, [])

  // Group by category
  const groups: Record<string, Faq[]> = {}
  for (const faq of faqs) {
    if (!groups[faq.category]) groups[faq.category] = []
    groups[faq.category].push(faq)
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="py-12 lg:py-20">
        <div className="mx-auto max-w-4xl px-4 lg:px-8">
          <div className="text-center mb-16">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-6">
              <MessageCircleQuestion className="h-8 w-8 text-primary" />
            </div>
            <h1 className="font-serif text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
              Frequently Asked Questions
            </h1>
            <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
              Got questions? We've got answers. If you can't find what you're looking for, feel free to contact our support team.
            </p>
          </div>

          <div className="space-y-12">
            {loading ? (
              <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary/20 border-t-primary" />
                <p className="text-sm">Loading FAQs…</p>
              </div>
            ) : Object.keys(groups).length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border bg-muted/40 p-12 text-center">
                <MessageCircleQuestion className="mx-auto mb-4 h-12 w-12 text-muted-foreground/50" />
                <p className="text-lg font-semibold text-foreground">No FAQs configured yet</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Our team is working on adding answers to common questions. In the meantime, feel free to{" "}
                  <a href="/contact" className="text-primary underline">contact us</a> directly.
                </p>
              </div>
            ) : Object.entries(groups).map(([category, items]) => (
              <div key={category}>
                <h2 className="font-serif text-2xl font-bold text-foreground mb-6">{category}</h2>
                <div className="space-y-4">
                  {items.map(faq => (
                    <details
                      key={faq.id}
                      className="group bg-card p-6 rounded-2xl shadow-sm border border-border [&_summary::-webkit-details-marker]:hidden"
                    >
                      <summary className="flex justify-between items-center font-semibold text-lg cursor-pointer text-foreground list-none">
                        {faq.question}
                        <span className="transition duration-300 group-open:-rotate-180 flex shrink-0 ml-4 items-center justify-center h-8 w-8 rounded-full bg-secondary/20 text-secondary">
                          <ChevronDown className="h-5 w-5" />
                        </span>
                      </summary>
                      <div className="text-muted-foreground mt-4 leading-relaxed bg-muted/50 p-4 rounded-xl border border-border/50">
                        {faq.answer}
                      </div>
                    </details>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}

