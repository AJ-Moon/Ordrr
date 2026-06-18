import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Trash2, Loader2, MailOpen, Mail } from "lucide-react"
import { toast } from "sonner"

interface ContactMessage {
  id: number
  name: string
  email: string
  phone: string
  subject: string
  message: string
  isRead: boolean
  createdAt: string
}

export default function AdminContactMessagesPage() {
  const [messages, setMessages] = useState<ContactMessage[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState<"all" | "unread">("all")

  const token = localStorage.getItem("admin_token")
  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` }

  const fetchMessages = () => {
    setIsLoading(true)
    fetch("/api/admin/contact-messages", { headers })
      .then((r) => r.json())
      .then(setMessages)
      .finally(() => setIsLoading(false))
  }

  useEffect(fetchMessages, [])

  const markRead = async (id: number) => {
    await fetch(`/api/admin/contact-messages/${id}/read`, { method: "PATCH", headers })
    setMessages((prev) => prev.map((m) => m.id === id ? { ...m, isRead: true } : m))
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this message?")) return
    try {
      await fetch(`/api/admin/contact-messages/${id}`, { method: "DELETE", headers })
      toast.success("Message deleted")
      setMessages((prev) => prev.filter((m) => m.id !== id))
    } catch {
      toast.error("Failed to delete")
    }
  }

  const displayed = filter === "unread" ? messages.filter((m) => !m.isRead) : messages
  const unreadCount = messages.filter((m) => !m.isRead).length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            Contact Messages
            {unreadCount > 0 && <Badge className="bg-primary text-primary-foreground">{unreadCount} unread</Badge>}
          </h1>
          <p className="text-sm text-muted-foreground">Customer inquiries from the contact form</p>
        </div>
        <div className="flex gap-2">
          <Button variant={filter === "all" ? "default" : "outline"} size="sm" onClick={() => setFilter("all")}>All</Button>
          <Button variant={filter === "unread" ? "default" : "outline"} size="sm" onClick={() => setFilter("unread")}>Unread</Button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>
      ) : displayed.length === 0 ? (
        <div className="py-16 text-center text-muted-foreground">No messages found.</div>
      ) : (
        <div className="space-y-3">
          {displayed.map((m) => (
            <Card key={m.id} className={m.isRead ? "" : "border-primary/40 bg-primary/5"}>
              <CardContent className="pt-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      {m.isRead ? <MailOpen className="h-4 w-4 text-muted-foreground" /> : <Mail className="h-4 w-4 text-primary" />}
                      <span className="font-semibold text-sm">{m.name}</span>
                      <span className="text-xs text-muted-foreground">{m.email}</span>
                      {m.phone && <span className="text-xs text-muted-foreground">{m.phone}</span>}
                      <span className="ml-auto text-xs text-muted-foreground">
                        {new Date(m.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                      </span>
                    </div>
                    <p className="text-sm font-medium mb-1">{m.subject}</p>
                    <p className="text-sm text-muted-foreground line-clamp-3">{m.message}</p>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    {!m.isRead && (
                      <Button variant="ghost" size="sm" className="text-primary" onClick={() => markRead(m.id)}>
                        Mark Read
                      </Button>
                    )}
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => handleDelete(m.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
