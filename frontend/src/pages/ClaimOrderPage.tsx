import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { QrCode, CheckCircle2, AlertCircle, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"

function authFetch(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem("auth_token")
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      // No X-Restaurant-ID needed: backend resolves tenant from the HTTP Host header
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  })
}

export default function ClaimOrderPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [receiptNumber, setReceiptNumber] = useState(searchParams.get("code") || "")
  const [phone, setPhone] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ orderId: string; pointsEarned: number } | null>(null)

  // Require login
  const user = (() => {
    try { return JSON.parse(localStorage.getItem("auth_user") || "null") } catch { return null }
  })()

  useEffect(() => {
    if (!user) {
      toast.error("Please log in to claim an order")
      navigate("/login?redirect=/claim-order")
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!receiptNumber.trim()) return

    setLoading(true)
    try {
      const res = await authFetch("/api/orders/claim", {
        method: "POST",
        body: JSON.stringify({
          receiptNumber: receiptNumber.trim(),
          phone: phone.trim() || undefined,
        }),
      })
      const data = await res.json()

      if (res.ok) {
        setResult({ orderId: data.orderId, pointsEarned: data.pointsEarned })
        if (data.pointsEarned > 0) {
          toast.success(`🎉 Order claimed! You earned ${data.pointsEarned} points.`)
        } else {
          toast.success("Order claimed successfully!")
        }
      } else {
        toast.error(data.detail || "Could not claim order. Please try again.")
      }
    } catch {
      toast.error("Network error. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  if (!user) return null

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="rounded-2xl border bg-card shadow-sm p-8">
          {result ? (
            /* Success state */
            <div className="text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100 mx-auto mb-4">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              </div>
              <h2 className="text-xl font-bold mb-2">Order Claimed!</h2>
              <p className="text-muted-foreground mb-1">Order <span className="font-mono font-semibold">{result.orderId}</span> has been linked to your account.</p>
              {result.pointsEarned > 0 && (
                <p className="text-amber-600 font-semibold mt-2">+{result.pointsEarned} points earned!</p>
              )}
              <div className="mt-6 flex gap-3">
                <Button variant="outline" className="flex-1" onClick={() => navigate("/history")}>
                  View Orders
                </Button>
                <Button className="flex-1" onClick={() => { setResult(null); setReceiptNumber(""); setPhone("") }}>
                  Claim Another
                </Button>
              </div>
            </div>
          ) : (
            /* Form state */
            <>
              <div className="text-center mb-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 mx-auto mb-3">
                  <QrCode className="h-6 w-6 text-primary" />
                </div>
                <h1 className="text-xl font-bold">Claim In-Store Order</h1>
                <p className="text-sm text-muted-foreground mt-1">
                  Enter your receipt or order number to link an in-store purchase to your account and earn points.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <Label htmlFor="receipt">Receipt / Order Number</Label>
                  <Input
                    id="receipt"
                    value={receiptNumber}
                    onChange={e => setReceiptNumber(e.target.value)}
                    placeholder="e.g. FH-12345"
                    className="mt-1.5"
                    required
                  />
                </div>

                <div>
                  <Label htmlFor="phone">
                    Phone Number <span className="text-muted-foreground text-xs">(if required by restaurant)</span>
                  </Label>
                  <Input
                    id="phone"
                    type="tel"
                    value={phone}
                    onChange={e => setPhone(e.target.value)}
                    placeholder="Your phone number"
                    className="mt-1.5"
                  />
                </div>

                <Button type="submit" className="w-full" disabled={loading || !receiptNumber.trim()}>
                  {loading ? (
                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Claiming…</>
                  ) : "Claim Order & Earn Points"}
                </Button>
              </form>

              <div className="mt-4 rounded-lg bg-muted/50 p-3 flex gap-2 text-xs text-muted-foreground">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>Orders can only be claimed once. Claims must be made within the allowed time window.</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
