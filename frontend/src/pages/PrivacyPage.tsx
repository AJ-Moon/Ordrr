import { useEffect, useState } from "react"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { ShieldCheck } from "lucide-react"

export default function PrivacyPage() {
  const [title, setTitle] = useState("Privacy Policy")
  const [content, setContent] = useState("")
  const [updatedAt, setUpdatedAt] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch("/api/faqs/content/privacy")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return
        setTitle(data.title || "Privacy Policy")
        setContent(data.content || "")
        if (data.updated_at) {
          setUpdatedAt(new Date(data.updated_at).toLocaleDateString("en-US", {
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
              <ShieldCheck className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="font-serif text-3xl font-bold md:text-4xl text-foreground">
                {title}
              </h1>
              {updatedAt && (
                <p className="text-muted-foreground mt-1">Last updated: {updatedAt}</p>
              )}
            </div>
          </div>

          {loading ? (
            <div className="py-12 text-sm text-muted-foreground">Loading privacy policy...</div>
          ) : content.trim() ? (
            <article className="whitespace-pre-wrap text-muted-foreground leading-relaxed">
              {content}
            </article>
          ) : (
            <div className="rounded-lg border bg-card p-5 text-sm text-muted-foreground">
              Privacy policy is not configured yet. Please check back later.
            </div>
          )}
        </div>
      </main>
      <Footer />
    </div>
  )
}
