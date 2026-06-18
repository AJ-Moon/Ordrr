import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Switch } from "@/components/ui/switch"
import { Pencil, Trash2, Plus, MapPin, Loader2 } from "lucide-react"
import { toast } from "sonner"

interface Branch {
  id: number
  name: string
  address: string
  city: string
  phone: string
  hours: string
  mapsUrl: string
  isOpen: boolean
  isDefault: boolean
}

const EMPTY: Omit<Branch, "id"> = {
  name: "", address: "", city: "", phone: "", hours: "", mapsUrl: "", isOpen: true, isDefault: false
}

export default function AdminBranchesPage() {
  const [branches, setBranches] = useState<Branch[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [form, setForm] = useState<Omit<Branch, "id">>(EMPTY)
  const [editId, setEditId] = useState<number | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  const token = localStorage.getItem("admin_token")
  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` }

  const fetchBranches = () => {
    setIsLoading(true)
    fetch("/api/admin/branches", { headers })
      .then((r) => r.json())
      .then(setBranches)
      .finally(() => setIsLoading(false))
  }

  useEffect(fetchBranches, [])

  const openAdd = () => { setForm(EMPTY); setEditId(null); setDialogOpen(true) }
  const openEdit = (b: Branch) => { setForm({ name: b.name, address: b.address, city: b.city, phone: b.phone, hours: b.hours, mapsUrl: b.mapsUrl || "", isOpen: b.isOpen, isDefault: b.isDefault }); setEditId(b.id); setDialogOpen(true) }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      const body = JSON.stringify({
        name: form.name, address: form.address, city: form.city,
        phone: form.phone, hours: form.hours, mapsUrl: form.mapsUrl,
        isOpen: form.isOpen, isDefault: form.isDefault,
      })
      const url = editId ? `/api/admin/branches/${editId}` : "/api/admin/branches"
      const method = editId ? "PUT" : "POST"
      const res = await fetch(url, { method, headers, body })
      if (!res.ok) throw new Error()
      toast.success(editId ? "Branch updated" : "Branch added")
      setDialogOpen(false)
      fetchBranches()
    } catch {
      toast.error("Failed to save branch")
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this branch?")) return
    try {
      const res = await fetch(`/api/admin/branches/${id}`, { method: "DELETE", headers })
      if (!res.ok) throw new Error()
      toast.success("Branch deleted")
      fetchBranches()
    } catch {
      toast.error("Failed to delete branch")
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Branches</h1>
          <p className="text-sm text-muted-foreground">Manage restaurant locations</p>
        </div>
        <Button onClick={openAdd}><Plus className="mr-2 h-4 w-4" />Add Branch</Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {branches.map((b) => (
            <Card key={b.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-base">{b.name}</CardTitle>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(b)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => handleDelete(b.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground space-y-1">
                <div className="flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5 shrink-0" /><span>{b.address}, {b.city}</span></div>
                <p>{b.phone}</p>
                <p>{b.hours}</p>
                <div className="flex items-center gap-3 pt-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${b.isOpen ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                    {b.isOpen ? "Open" : "Closed"}
                  </span>
                  {b.isDefault && <span className="rounded-full px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700">Default</span>}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editId ? "Edit Branch" : "Add Branch"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {(["name", "address", "city", "phone", "hours", "mapsUrl"] as const).map((field) => (
              <div key={field} className="space-y-1.5">
                <Label className="capitalize">{field === "mapsUrl" ? "Maps URL" : field}</Label>
                <Input value={form[field]} onChange={(e) => setForm({ ...form, [field]: e.target.value })} />
              </div>
            ))}
            <div className="flex items-center justify-between">
              <Label>Is Open</Label>
              <Switch checked={form.isOpen} onCheckedChange={(v) => setForm({ ...form, isOpen: v })} />
            </div>
            <div className="flex items-center justify-between">
              <Label>Default Branch</Label>
              <Switch checked={form.isDefault} onCheckedChange={(v) => setForm({ ...form, isDefault: v })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving...</> : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
