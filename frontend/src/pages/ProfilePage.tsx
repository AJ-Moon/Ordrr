import { useEffect, useState } from "react"
import { Navigate } from "react-router-dom"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { User, Loader2, ShieldCheck } from "lucide-react"
import { useAuth } from "@/contexts/AuthContext"
import { toast } from "sonner"
import { track } from "@/lib/analytics"

type ConsentChannel = "email" | "sms" | "whatsapp"

const CONSENT_LABELS: Record<ConsentChannel, { title: string; description: string }> = {
  email: { title: "Email", description: "Offers, menu news, and order follow-ups by email." },
  sms: { title: "SMS", description: "Time-sensitive offers and order-related text messages." },
  whatsapp: { title: "WhatsApp", description: "Restaurant updates and approved offers on WhatsApp." },
}

export default function ProfilePage() {
  const { user, token, updateUser } = useAuth()
  const [firstName, setFirstName] = useState(user?.firstName || "")
  const [lastName, setLastName] = useState(user?.lastName || "")
  const [phone, setPhone] = useState(user?.phone || "")
  const [isSaving, setIsSaving] = useState(false)
  const [isConsentLoading, setIsConsentLoading] = useState(true)
  const [isConsentSaving, setIsConsentSaving] = useState(false)
  const [consents, setConsents] = useState<Record<ConsentChannel, boolean>>({
    email: false,
    sms: false,
    whatsapp: false,
  })

  useEffect(() => {
    if (!token) return
    fetch("/api/v1/customers/me/consents", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Failed to load communication preferences")
        const data = await response.json()
        const next = { email: false, sms: false, whatsapp: false }
        for (const consent of data.consents || []) {
          if (consent.channel in next) {
            next[consent.channel as ConsentChannel] = consent.status === "granted"
          }
        }
        setConsents(next)
      })
      .catch(() => toast.error("Could not load communication preferences"))
      .finally(() => setIsConsentLoading(false))
  }, [token])

  if (!user) return <Navigate to="/login" state={{ from: "/profile" }} replace />

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSaving(true)
    try {
      const res = await fetch("/api/auth/me", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ firstName, lastName, phone }),
      })
      if (!res.ok) throw new Error("Failed to update profile")
      const updated = await res.json()
      updateUser({ ...user, ...updated })
      toast.success("Profile updated!")
    } catch {
      toast.error("Could not update profile")
    } finally {
      setIsSaving(false)
    }
  }

  const handleConsentSave = async () => {
    setIsConsentSaving(true)
    try {
      const response = await fetch("/api/v1/customers/me/consents", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          consents: (Object.keys(consents) as ConsentChannel[]).map((channel) => ({
            channel,
            status: consents[channel] ? "granted" : "withdrawn",
            source: "account_settings",
            policyVersion: "1",
          })),
        }),
      })
      if (!response.ok) throw new Error("Failed to save communication preferences")
      track("consent_updated", {
        properties: { channels: consents },
        consentState: "essential",
      })
      toast.success("Communication preferences updated")
    } catch {
      toast.error("Could not update communication preferences")
    } finally {
      setIsConsentSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="pb-24 md:pb-0">
        <div className="mx-auto max-w-2xl px-4 py-8 lg:px-8">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <User className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="font-serif text-2xl font-bold text-foreground">My Profile</h1>
              <p className="text-sm text-muted-foreground">{user.email}</p>
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Personal Information</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSave} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="firstName">First Name</Label>
                    <Input
                      id="firstName"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="lastName">Last Name</Label>
                    <Input
                      id="lastName"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="phone">Phone Number</Label>
                  <Input
                    id="phone"
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+1 234 567 8900"
                  />
                  <p className="text-xs text-muted-foreground">
                    Used for order tracking. Keep it updated.
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label>Email</Label>
                  <Input value={user.email} disabled className="bg-muted" />
                </div>
                <Button type="submit" disabled={isSaving}>
                  {isSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving...</> : "Save Changes"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-primary" />
                Communication Preferences
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <p className="text-sm text-muted-foreground">
                Choose which optional marketing channels this restaurant may use. Essential order messages are handled separately.
              </p>
              {(Object.keys(CONSENT_LABELS) as ConsentChannel[]).map((channel) => (
                <div key={channel} className="flex items-center justify-between gap-6 border-b pb-4 last:border-0 last:pb-0">
                  <div>
                    <Label htmlFor={`consent-${channel}`}>{CONSENT_LABELS[channel].title}</Label>
                    <p className="mt-1 text-xs text-muted-foreground">{CONSENT_LABELS[channel].description}</p>
                  </div>
                  <Switch
                    id={`consent-${channel}`}
                    checked={consents[channel]}
                    disabled={isConsentLoading || isConsentSaving}
                    onCheckedChange={(checked) => setConsents((current) => ({ ...current, [channel]: checked }))}
                  />
                </div>
              ))}
              <Button type="button" onClick={handleConsentSave} disabled={isConsentLoading || isConsentSaving}>
                {isConsentSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving...</> : "Save Preferences"}
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
      <Footer />
    </div>
  )
}
