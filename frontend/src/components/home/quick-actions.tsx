import { Link } from "react-router-dom"
import { ShoppingBag, Star, MapPin, Phone } from "lucide-react"
import { useRestaurant } from "@/contexts/RestaurantContext"

const actions = [
  {
    icon: ShoppingBag,
    label: "Order Now",
    href: "/menu",
    description: "Skip the line",
  },
  {
    icon: Star,
    label: "Points & Rewards",
    href: "/points",
    description: "Earn on every order",
  },
  {
    icon: MapPin,
    label: "Branch Locator",
    href: "/branches",
    description: "Find near you",
  },
  {
    icon: Phone,
    label: "Contact Us",
    href: "/contact",
    description: "Get in touch",
  },
]

export function QuickActions() {
  const { primaryColor } = useRestaurant()

  return (
    <section className="border-b border-border bg-white py-4">
      <div className="mx-auto max-w-7xl px-4 lg:px-8">
        {/* Mobile: horizontal scroll strip | Desktop: 4-column grid */}
        <div className="flex gap-3 overflow-x-auto scrollbar-hide pb-1 sm:grid sm:grid-cols-4 sm:overflow-visible sm:pb-0">
          {actions.map((action) => {
            const Icon = action.icon
            return (
              <Link
                key={action.label}
                to={action.href}
                className="group flex shrink-0 items-center gap-3 rounded-xl border border-border bg-white px-4 py-3 transition-all duration-200 hover:border-border hover:shadow-md sm:shrink"
                style={{
                  borderLeftWidth: 4,
                  borderLeftColor: primaryColor,
                }}
              >
                <Icon
                  className="h-4 w-4 shrink-0 transition-colors"
                  style={{ color: primaryColor }}
                />
                <div className="min-w-0">
                  <p className="whitespace-nowrap text-sm font-semibold text-foreground">
                    {action.label}
                  </p>
                  <p className="whitespace-nowrap text-xs text-muted-foreground">
                    {action.description}
                  </p>
                </div>
              </Link>
            )
          })}
        </div>
      </div>
    </section>
  )
}
