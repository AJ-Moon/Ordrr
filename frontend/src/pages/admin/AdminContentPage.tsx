import { useEffect, useState } from "react"
import { Plus, Pencil, Trash2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

function adminFetch(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem("admin_token")
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  })
}

interface Faq { id: number; question: string; answer: string; category: string; orderIndex: number }
interface ContentPage { slug: string; title: string; content: string }

// ── FAQs tab ─────────────────────────────────────────────────────────────────
function FaqsTab() {
  const [faqs, setFaqs] = useState<Faq[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Faq | null>(null)
  const [form, setForm] = useState({ question: "", answer: "", category: "General", orderIndex: 0 })
  const [saving, setSaving] = useState(false)

  const fetch_ = async () => {
    setLoading(true)
    try {
      const res = await adminFetch("/api/admin/faqs")
      if (res.ok) setFaqs(await res.json())
    } finally { setLoading(false) }
  }

  useEffect(() => { fetch_() }, [])

  const openAdd = () => { setEditing(null); setForm({ question: "", answer: "", category: "General", orderIndex: 0 }); setOpen(true) }
  const openEdit = (f: Faq) => { setEditing(f); setForm({ question: f.question, answer: f.answer, category: f.category, orderIndex: f.orderIndex }); setOpen(true) }

  const save = async () => {
    setSaving(true)
    try {
      const url = editing ? `/api/admin/faqs/${editing.id}` : "/api/admin/faqs"
      const method = editing ? "PUT" : "POST"
      const res = await adminFetch(url, { method, body: JSON.stringify(form) })
      if (res.ok) {
        const saved = await res.json()
        setFaqs(prev => editing ? prev.map(f => (f.id === editing.id ? saved : f)) : [...prev, saved])
        setOpen(false)
      }
    } finally { setSaving(false) }
  }

  const remove = async (id: number) => {
    if (!confirm("Delete this FAQ?")) return
    await adminFetch(`/api/admin/faqs/${id}`, { method: "DELETE" })
    setFaqs(prev => prev.filter(f => f.id !== id))
  }

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button onClick={openAdd}><Plus className="mr-2 h-4 w-4" /> Add FAQ</Button>
      </div>
      <div className="rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Question</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Order</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={4} className="text-center py-8 text-muted-foreground">Loading…</TableCell></TableRow>
            ) : faqs.map(faq => (
              <TableRow key={faq.id}>
                <TableCell>
                  <div className="font-medium">{faq.question}</div>
                  <div className="text-xs text-muted-foreground line-clamp-1 max-w-[320px]">{faq.answer}</div>
                </TableCell>
                <TableCell>{faq.category}</TableCell>
                <TableCell>{faq.orderIndex}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(faq)}><Pencil className="h-4 w-4" /></Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => remove(faq.id)}><Trash2 className="h-4 w-4" /></Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>{editing ? "Edit FAQ" : "Add FAQ"}</DialogTitle></DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="space-y-2">
              <Label>Question</Label>
              <Input value={form.question} onChange={e => setForm(p => ({ ...p, question: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>Answer</Label>
              <Textarea rows={4} value={form.answer} onChange={e => setForm(p => ({ ...p, answer: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Category</Label>
                <Input value={form.category} onChange={e => setForm(p => ({ ...p, category: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Order Index</Label>
                <Input type="number" value={form.orderIndex} onChange={e => setForm(p => ({ ...p, orderIndex: parseInt(e.target.value) || 0 }))} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} disabled={saving || !form.question}>{saving ? "Saving…" : "Save"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ── Content tab ───────────────────────────────────────────────────────────────
function ContentTab({ slug }: { slug: string }) {
  const [page, setPage] = useState<ContentPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setLoading(true)
    adminFetch(`/api/admin/content/${slug}`).then(r => r.ok ? r.json() : null).then(d => { setPage(d); setLoading(false) })
  }, [slug])

  const save = async () => {
    if (!page) return
    setSaving(true)
    const res = await adminFetch(`/api/admin/content/${slug}`, {
      method: "PUT", body: JSON.stringify({ title: page.title, content: page.content })
    })
    if (res.ok) { setSaved(true); setTimeout(() => setSaved(false), 2000) }
    setSaving(false)
  }

  if (loading) return <div className="py-12 text-center text-muted-foreground">Loading…</div>
  if (!page) return <div className="py-12 text-center text-muted-foreground">Page not found</div>

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Page Title</Label>
        <Input value={page.title} onChange={e => setPage(p => p ? { ...p, title: e.target.value } : p)} />
      </div>
      <div className="space-y-2">
        <Label>Content (Markdown supported)</Label>
        <Textarea
          rows={20}
          className="font-mono text-sm"
          value={page.content}
          onChange={e => setPage(p => p ? { ...p, content: e.target.value } : p)}
        />
      </div>
      <Button onClick={save} disabled={saving}>
        <Save className="mr-2 h-4 w-4" />
        {saving ? "Saving…" : saved ? "Saved!" : "Save Changes"}
      </Button>
    </div>
  )
}

export default function AdminContentPage() {
  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Content</h1>
        <p className="text-sm text-muted-foreground">Manage FAQs and page content</p>
      </div>
      <Tabs defaultValue="faqs">
        <TabsList className="mb-6">
          <TabsTrigger value="faqs">FAQs</TabsTrigger>
          <TabsTrigger value="privacy">Privacy Policy</TabsTrigger>
          <TabsTrigger value="terms">Terms of Service</TabsTrigger>
        </TabsList>
        <TabsContent value="faqs"><FaqsTab /></TabsContent>
        <TabsContent value="privacy"><ContentTab slug="privacy" /></TabsContent>
        <TabsContent value="terms"><ContentTab slug="terms" /></TabsContent>
      </Tabs>
    </div>
  )
}
