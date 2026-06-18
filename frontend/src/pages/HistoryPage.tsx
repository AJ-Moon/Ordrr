import { useState, useEffect } from "react"
import { Navigate, Link } from "react-router-dom"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ShoppingBag, RefreshCw, Calendar, Loader2, UtensilsCrossed } from "lucide-react"
import { useAuth } from "@/contexts/AuthContext"
import { useCart } from "@/contexts/CartContext"
import { toast } from "sonner"

interface OrderItem {
  menuItemId: number
  name: string
  quantity: number
  price: number
}

interface Order {
  id: string
  items: OrderItem[]
  total: number
  subtotal: number
  status: string
  orderType: string
  paymentMethod: string
  address: string
  pointsEarned: number
  createdAt: string
}

const STATUS_COLORS: Record<string, string> = {
  placed: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  confirmed: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400",
  preparing: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  ready: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
  out_for_delivery: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  delivered: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  cancelled: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
}

export default function HistoryPage() {
  const { user, token } = useAuth()
  const { addItem } = useCart()
  const [orders, setOrders] = useState<Order[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    fetch("/api/orders/history", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data: Order[]) => setOrders(data))
      .catch(() => toast.error("Could not load order history"))
      .finally(() => setIsLoading(false))
  }, [token])

  if (!user) return <Navigate to="/login" state={{ from: "/history" }} replace />

  const handleReorder = (order: Order) => {
    order.items.forEach((item) => {
      addItem({
        menuItemId: item.menuItemId,
        name: item.name,
        price: item.price,
        image: "",
      }, item.quantity)
    })
    toast.success("Items added to cart!")
  }

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString("en-US", {
        year: "numeric", month: "long", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      })
    } catch {
      return iso
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="pb-24 md:pb-0">
        <section className="bg-accent py-10 lg:py-14">
          <div className="mx-auto max-w-7xl px-4 lg:px-8">
            <h1 className="font-serif text-3xl font-bold text-accent-foreground md:text-4xl">
              Previous Orders
            </h1>
            <p className="mt-2 text-accent-foreground/70">Your complete order history</p>
          </div>
        </section>

        <div className="mx-auto max-w-4xl px-4 py-8 lg:px-8">
          {isLoading ? (
            <div className="flex justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : orders.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-muted">
                <ShoppingBag className="h-10 w-10 text-muted-foreground" />
              </div>
              <h2 className="mb-2 font-serif text-xl font-semibold text-foreground">No orders yet</h2>
              <p className="mb-6 text-muted-foreground">Your order history will appear here.</p>
              <Button asChild>
                <Link to="/menu">
                  <UtensilsCrossed className="mr-2 h-4 w-4" />
                  Explore Menu
                </Link>
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {orders.map((order) => (
                <Card key={order.id} className="overflow-hidden">
                  <CardHeader className="flex flex-row items-start justify-between gap-4 bg-muted/30 pb-3">
                    <div>
                      <CardTitle className="font-mono text-lg">{order.id}</CardTitle>
                      <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
                        <Calendar className="h-3.5 w-3.5" />
                        {formatDate(order.createdAt)}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${STATUS_COLORS[order.status] || ""}`}>
                        {order.status.replace(/_/g, " ")}
                      </span>
                      <Badge variant="outline" className="capitalize text-xs">{order.orderType}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-4">
                    <div className="mb-4 space-y-1.5 text-sm">
                      {order.items.map((item, i) => (
                        <div key={i} className="flex justify-between text-muted-foreground">
                          <span>{item.name} × {item.quantity}</span>
                          <span>${(item.price * item.quantity).toFixed(2)}</span>
                        </div>
                      ))}
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold text-foreground">Total: ${(order.total || 0).toFixed(2)}</p>
                        <p className="text-xs text-muted-foreground capitalize">
                          {order.paymentMethod === "cash" ? "Cash on delivery" : "Card payment"}
                        </p>
                        {(order.pointsEarned || 0) > 0 && (
                          <p className="text-xs text-primary">+{order.pointsEarned} pts earned</p>
                        )}
                      </div>
                      <Button variant="outline" size="sm" onClick={() => handleReorder(order)}>
                        <RefreshCw className="mr-2 h-3.5 w-3.5" />
                        Reorder
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </main>
      <Footer />
    </div>
  )
}
