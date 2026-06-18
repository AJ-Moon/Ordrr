import { useParams, useLocation, Link } from "react-router-dom"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import { CheckCircle2, ShoppingBag, MapPin, Clock, Star } from "lucide-react"
import { Separator } from "@/components/ui/separator"

interface OrderItem {
  name: string
  quantity: number
  price: number
}

interface Order {
  id: string
  items: OrderItem[]
  subtotal: number
  discountAmount: number
  deliveryCharge: number
  total: number
  status: string
  orderType: string
  paymentMethod: string
  address: string
  guestName: string
  pointsEarned: number
  createdAt: string
}

export default function OrderConfirmationPage() {
  const { orderId } = useParams<{ orderId: string }>()
  const location = useLocation()
  const order: Order | undefined = location.state?.order
  const trackPhone: string = location.state?.trackPhone || ""

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="pb-24 md:pb-0">
        <div className="mx-auto max-w-lg px-4 py-12 text-center">
          {/* Success Icon */}
          <div className="mb-6 flex items-center justify-center">
            <div className="relative flex h-24 w-24 items-center justify-center rounded-full bg-green-50 dark:bg-green-950">
              <CheckCircle2 className="h-14 w-14 text-green-500" />
            </div>
          </div>

          <h1 className="font-serif text-3xl font-bold text-foreground">Order Placed!</h1>
          <p className="mt-2 text-muted-foreground">
            Thank you! Your order has been received and is being processed.
          </p>

          {/* Order Number */}
          <div className="mt-6 rounded-xl border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Order Number</p>
            <p className="font-mono text-2xl font-bold text-primary">{orderId || order?.id}</p>
            <p className="mt-1 text-xs text-muted-foreground">Save this for tracking your order</p>
          </div>

          {/* Order Details */}
          {order && (
            <div className="mt-6 rounded-xl border border-border bg-card text-left">
              <div className="p-4">
                <h2 className="mb-3 font-semibold text-foreground">Order Summary</h2>
                <div className="space-y-2 text-sm">
                  {order.items.map((item, i) => (
                    <div key={i} className="flex justify-between text-muted-foreground">
                      <span>{item.name} × {item.quantity}</span>
                      <span>${(item.price * item.quantity).toFixed(2)}</span>
                    </div>
                  ))}
                </div>
                <Separator className="my-3" />
                <div className="space-y-1.5 text-sm">
                  <div className="flex justify-between text-muted-foreground">
                    <span>Subtotal</span>
                    <span>${(order.subtotal || 0).toFixed(2)}</span>
                  </div>
                  {(order.deliveryCharge || 0) > 0 && (
                    <div className="flex justify-between text-muted-foreground">
                      <span>Delivery</span>
                      <span>${order.deliveryCharge.toFixed(2)}</span>
                    </div>
                  )}
                  {(order.discountAmount || 0) > 0 && (
                    <div className="flex justify-between text-green-600">
                      <span>Discount</span>
                      <span>-${order.discountAmount.toFixed(2)}</span>
                    </div>
                  )}
                  <div className="flex justify-between font-semibold text-foreground">
                    <span>Total</span>
                    <span>${(order.total || 0).toFixed(2)}</span>
                  </div>
                </div>
              </div>

              <Separator />

              <div className="grid grid-cols-2 gap-3 p-4 text-sm">
                <div className="flex items-start gap-2 text-muted-foreground">
                  <ShoppingBag className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <p className="font-medium text-foreground capitalize">{order.orderType}</p>
                    <p>{order.paymentMethod === "cash" ? "Cash on delivery" : "Card payment"}</p>
                  </div>
                </div>
                {order.address && (
                  <div className="flex items-start gap-2 text-muted-foreground">
                    <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <div>
                      <p className="font-medium text-foreground">Delivery to</p>
                      <p className="line-clamp-2">{order.address}</p>
                    </div>
                  </div>
                )}
                <div className="flex items-start gap-2 text-muted-foreground">
                  <Clock className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <p className="font-medium text-foreground">Status</p>
                    <p className="capitalize">{order.status}</p>
                  </div>
                </div>
                {(order.pointsEarned || 0) > 0 && (
                  <div className="flex items-start gap-2 text-muted-foreground">
                    <Star className="mt-0.5 h-4 w-4 shrink-0 text-secondary" />
                    <div>
                      <p className="font-medium text-foreground">Points Earned</p>
                      <p>+{order.pointsEarned} pts</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* CTA Buttons */}
          <div className="mt-8 flex flex-col gap-3">
            <Button asChild size="lg">
              <Link to={`/track?order_id=${orderId || order?.id}&phone=${encodeURIComponent(trackPhone)}`}>Track Your Order</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/menu">Continue Ordering</Link>
            </Button>
          </div>

          <p className="mt-6 text-xs text-muted-foreground">
            Need help?{" "}
            <Link to="/contact" className="text-primary underline">Contact us</Link>
          </p>
        </div>
      </main>
      <Footer />
    </div>
  )
}
