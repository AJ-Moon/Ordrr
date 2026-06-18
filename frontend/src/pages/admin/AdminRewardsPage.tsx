import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Switch } from "@/components/ui/switch"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

interface RewardSettings {
  mode: "points" | "item-count"
  pointsPerUnit: number
  unitAmount: number
  minRedeem: number
  maxDiscount: number
  conversionRate: number
  eligibleCategory: string
  eligibleItemId: number | null
  requiredCount: number
  freeItemId: number | null
  autoApply: boolean
}

const DEFAULTS: RewardSettings = {
  mode: "points",
  pointsPerUnit: 1,
  unitAmount: 10,
  minRedeem: 100,
  maxDiscount: 10,
  conversionRate: 0.1,
  eligibleCategory: "",
  eligibleItemId: null,
  requiredCount: 10,
  freeItemId: null,
  autoApply: false,
}

export default function AdminRewardsPage() {
  const [settings, setSettings] = useState<RewardSettings>(DEFAULTS)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)

  const token = localStorage.getItem("admin_token")
  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` }

  useEffect(() => {
    fetch("/api/admin/reward-settings", { headers })
      .then((r) => r.json())
      .then((data) => setSettings({ ...DEFAULTS, ...data }))
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }, [])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      const res = await fetch("/api/admin/reward-settings", {
        method: "PUT", headers, body: JSON.stringify(settings),
      })
      if (!res.ok) throw new Error()
      toast.success("Reward settings saved")
    } catch {
      toast.error("Failed to save")
    } finally {
      setIsSaving(false)
    }
  }

  const num = (field: keyof RewardSettings) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setSettings({ ...settings, [field]: parseFloat(e.target.value) || 0 })

  if (isLoading) return <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Rewards Configuration</h1>
        <p className="text-sm text-muted-foreground">Configure how customers earn and redeem rewards</p>
      </div>

      <Tabs value={settings.mode} onValueChange={(v) => setSettings({ ...settings, mode: v as "points" | "item-count" })}>
        <TabsList className="w-full">
          <TabsTrigger value="points" className="flex-1">Points Mode</TabsTrigger>
          <TabsTrigger value="item-count" className="flex-1">Item Count Mode</TabsTrigger>
        </TabsList>

        <TabsContent value="points">
          <Card>
            <CardHeader>
              <CardTitle>Points Rewards</CardTitle>
              <CardDescription>Customers earn points per dollar spent and redeem for discounts.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>Points per ${"{unitAmount}"} spent</Label>
                  <Input type="number" value={settings.pointsPerUnit} onChange={num("pointsPerUnit")} min={0} step={0.1} />
                </div>
                <div className="space-y-1.5">
                  <Label>Unit Amount ($)</Label>
                  <Input type="number" value={settings.unitAmount} onChange={num("unitAmount")} min={1} />
                </div>
                <div className="space-y-1.5">
                  <Label>Minimum points to redeem</Label>
                  <Input type="number" value={settings.minRedeem} onChange={num("minRedeem")} min={1} />
                </div>
                <div className="space-y-1.5">
                  <Label>Max discount per order ($)</Label>
                  <Input type="number" value={settings.maxDiscount} onChange={num("maxDiscount")} min={0} step={0.5} />
                </div>
                <div className="space-y-1.5">
                  <Label>Conversion rate (points → $)</Label>
                  <Input type="number" value={settings.conversionRate} onChange={num("conversionRate")} min={0} step={0.01} />
                  <p className="text-xs text-muted-foreground">e.g. 0.10 means 10 points = $1</p>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <Label>Auto-apply points at checkout</Label>
                <Switch checked={settings.autoApply} onCheckedChange={(v) => setSettings({ ...settings, autoApply: v })} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="item-count">
          <Card>
            <CardHeader>
              <CardTitle>Buy X Get Free Item</CardTitle>
              <CardDescription>Customers get a free item after ordering a specific item N times.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>Eligible Category</Label>
                  <Input value={settings.eligibleCategory} onChange={(e) => setSettings({ ...settings, eligibleCategory: e.target.value })} placeholder="e.g. burgers" />
                </div>
                <div className="space-y-1.5">
                  <Label>Eligible Item ID (optional)</Label>
                  <Input type="number" value={settings.eligibleItemId || ""} onChange={(e) => setSettings({ ...settings, eligibleItemId: parseInt(e.target.value) || null })} />
                </div>
                <div className="space-y-1.5">
                  <Label>Required purchases</Label>
                  <Input type="number" value={settings.requiredCount} onChange={num("requiredCount")} min={1} />
                </div>
                <div className="space-y-1.5">
                  <Label>Free Item ID</Label>
                  <Input type="number" value={settings.freeItemId || ""} onChange={(e) => setSettings({ ...settings, freeItemId: parseInt(e.target.value) || null })} />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Button onClick={handleSave} disabled={isSaving} size="lg">
        {isSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving...</> : "Save Settings"}
      </Button>
    </div>
  )
}
