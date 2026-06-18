import { useEffect, useState } from "react"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { FileText } from "lucide-react"

export default function TermsPage() {
  const [title, setTitle] = useState("Terms of Service")
  const [content, setContent] = useState("")
  const [effectiveDate, setEffectiveDate] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch("/api/faqs/content/terms")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return
        setTitle(data.title || "Terms of Service")
        setContent(data.content || "")
        if (data.updated_at) {
          setEffectiveDate(new Date(data.updated_at).toLocaleDateString("en-US", {
            year: "numeric", month: "long", day: "numeric"
          }))
        }
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="py-12 lg:py-20">
        <div className="mx-auto max-w-4xl px-4 lg:px-8">
          <div className="flex items-center gap-4 mb-10 border-b border-border pb-8">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
              <FileText className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="font-serif text-3xl font-bold md:text-4xl text-foreground">
                {title}
              </h1>
              {effectiveDate && (
                <p className="text-muted-foreground mt-1">Effective Date: {effectiveDate}</p>
              )}
            </div>
          </div>

          {loading ? (
            <div className="py-12 text-sm text-muted-foreground">Loading terms...</div>
          ) : content.trim() ? (
            <article className="whitespace-pre-wrap text-muted-foreground leading-relaxed">
              {content}
            </article>
          ) : (
            <div className="rounded-lg border bg-card p-5 text-sm text-muted-foreground">
              Terms are not configured yet. Please check back later.
            </div>
          )}
        </div>
      </main>
      <Footer />
    </div>
  )
}
