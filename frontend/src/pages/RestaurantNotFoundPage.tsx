import { UtensilsCrossed } from "lucide-react"

export default function RestaurantNotFoundPage() {
  return (
    <div className="min-h-screen bg-muted/30 flex items-center justify-center p-6">
      <div className="text-center max-w-sm">
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
          <UtensilsCrossed className="h-8 w-8 text-muted-foreground" />
        </div>
        <h1 className="text-2xl font-bold mb-2">Restaurant Not Found</h1>
        <p className="text-muted-foreground text-sm">
          This domain is not associated with any restaurant on our platform. If
          you believe this is a mistake, please contact your restaurant or our
          support team.
        </p>
      </div>
    </div>
  )
}
