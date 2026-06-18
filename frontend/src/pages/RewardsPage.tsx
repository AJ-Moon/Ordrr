import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import {
  Gift,
  Star,
  Trophy,
  Zap,
  Crown,
  Utensils,
  Percent,
  Check,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/contexts/AuthContext"

const tiers = [
  {
    name: "Bronze",
    icon: Star,
    pointsRequired: 0,
    benefits: ["5% back on all orders", "Birthday reward", "Early access to deals"],
    color: "from-amber-600 to-amber-800",
  },
  {
    name: "Silver",
    icon: Zap,
    pointsRequired: 500,
    benefits: ["10% back on all orders", "Birthday reward", "Free delivery on orders $25+", "Monthly bonus points"],
    color: "from-slate-400 to-slate-600",
  },
  {
    name: "Gold",
    icon: Trophy,
    pointsRequired: 1500,
    benefits: ["15% back on all orders", "Birthday reward", "Free delivery always", "Weekly bonus points", "Exclusive menu items"],
    color: "from-yellow-500 to-amber-600",
  },
  {
    name: "Platinum",
    icon: Crown,
    pointsRequired: 5000,
    benefits: ["20% back on all orders", "Birthday reward", "Free delivery always", "Daily bonus points", "Exclusive menu items", "VIP support", "Surprise rewards"],
    color: "from-slate-300 to-slate-500",
  },
]

const earnWays = (pointsPerDollar: number) => [
  { icon: Utensils, title: "Order Food", description: `Earn ${pointsPerDollar} point${pointsPerDollar !== 1 ? "s" : ""} for every $1 spent`, points: `${pointsPerDollar}pt / $1` },
  { icon: Gift, title: "Refer Friends", description: "Get 100 points for each friend who joins", points: "100pts" },
  { icon: Star, title: "Write Reviews", description: "Share your experience and earn points", points: "25pts" },
]

const rewards = [
  { name: "Free Side Dish", points: 150, image: "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=200&h=200&fit=crop" },
  { name: "Free Drink", points: 100, image: "https://images.unsplash.com/photo-1437418747212-8d9709afab22?w=200&h=200&fit=crop" },
  { name: "Free Dessert", points: 200, image: "https://images.unsplash.com/photo-1551024601-bec78aea704b?w=200&h=200&fit=crop" },
  { name: "$10 Off Order", points: 300, image: "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=200&h=200&fit=crop" },
  { name: "Free Main Course", points: 500, image: "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=200&h=200&fit=crop" },
  { name: "Free Meal for Two", points: 800, image: "https://images.unsplash.com/photo-1432139509613-5c4255815697?w=200&h=200&fit=crop" },
]

export default function RewardsPage() {
  const { user, token } = useAuth()
  const [currentPoints, setCurrentPoints] = useState(0)
  const [minRedeem, setMinRedeem] = useState(100)
  const [pointsPerDollar, setPointsPerDollar] = useState(10)

  useEffect(() => {
    fetch("/api/rewards/settings")
      .then((r) => r.json())
      .then((d) => {
        setMinRedeem(d.minRedeem ?? 100)
        setPointsPerDollar(d.pointsPerDollar ?? 10)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!token) return
    fetch("/api/rewards/points", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((data) => setCurrentPoints(data.points ?? 0))
      .catch(() => {})
  }, [token])

  const currentTier = currentPoints >= 5000 ? "Platinum" : currentPoints >= 1500 ? "Gold" : currentPoints >= 500 ? "Silver" : "Bronze"
  const redeemProgress = Math.min((currentPoints / minRedeem) * 100, 100)

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        {/* Hero */}
        <section className="relative py-20 bg-linear-to-br from-primary via-primary/90 to-primary/80 overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.1),transparent_50%)]" />
          <div className="container mx-auto px-4 relative z-10">
            <div className="max-w-3xl mx-auto text-center text-primary-foreground">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/20 backdrop-blur-sm mb-6">
                <Gift className="w-5 h-5" />
                <span className="font-medium">Flavor Rewards Program</span>
              </div>
              <h1 className="font-serif text-4xl md:text-5xl lg:text-6xl font-bold mb-6 text-balance">
                Earn Points. Get Rewards.
              </h1>
              <p className="text-lg md:text-xl text-primary-foreground/90 mb-8">
                Join our rewards program and start earning points with every order. The more you order, the more you save!
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                {user ? (
                  <Button size="lg" variant="secondary" className="font-semibold" asChild>
                    <Link to="/points">View My Points</Link>
                  </Button>
                ) : (
                  <>
                    <Button size="lg" variant="secondary" className="font-semibold" asChild>
                      <Link to="/login">Join Now - It&apos;s Free</Link>
                    </Button>
                    <Button size="lg" variant="outline" className="bg-transparent border-white/30 text-primary-foreground hover:bg-white/10" asChild>
                      <Link to="/login">Sign In to View Points</Link>
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* Current Status */}
        <section className="py-12 bg-muted/30">
          <div className="container mx-auto px-4">
            <Card className="max-w-2xl mx-auto border-2 border-primary/20">
              <CardHeader className="text-center pb-2">
                <CardTitle className="font-serif text-2xl">Your Rewards Status</CardTitle>
                <CardDescription>Keep ordering to reach the next tier!</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-3 rounded-full bg-linear-to-br from-slate-400 to-slate-600">
                      <Zap className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <p className="font-semibold">{user ? `${currentTier} Member` : "Guest"}</p>
                      <p className="text-sm text-muted-foreground">{currentPoints} points</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-primary">
                      {currentPoints >= minRedeem
                        ? "Ready to redeem!"
                        : `${minRedeem - currentPoints} pts`}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {currentPoints >= minRedeem ? "Use at checkout" : "until first redeem"}
                    </p>
                  </div>
                </div>
                <div className="space-y-2">
                  <Progress value={redeemProgress} className="h-3" />
                  <div className="flex justify-between text-sm text-muted-foreground">
                    <span>0 pts</span>
                    <span>{minRedeem} pts (redeem threshold)</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* How to Earn */}
        <section className="py-16">
          <div className="container mx-auto px-4">
            <div className="text-center mb-12">
              <h2 className="font-serif text-3xl md:text-4xl font-bold text-foreground mb-4">Ways to Earn Points</h2>
              <p className="text-muted-foreground text-lg max-w-2xl mx-auto">Multiple ways to earn points and unlock delicious rewards</p>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl mx-auto">
              {earnWays(pointsPerDollar).map((way) => (
                <Card key={way.title} className="text-center hover:shadow-lg transition-shadow">
                  <CardContent className="pt-8 pb-6">
                    <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-primary/10 flex items-center justify-center">
                      <way.icon className="w-8 h-8 text-primary" />
                    </div>
                    <h3 className="font-semibold text-lg mb-2">{way.title}</h3>
                    <p className="text-sm text-muted-foreground mb-3">{way.description}</p>
                    <span className="inline-block px-3 py-1 rounded-full bg-secondary text-secondary-foreground font-semibold text-sm">
                      {way.points}
                    </span>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Membership Tiers */}
        <section className="py-16 bg-muted/30">
          <div className="container mx-auto px-4">
            <div className="text-center mb-12">
              <h2 className="font-serif text-3xl md:text-4xl font-bold text-foreground mb-4">Membership Tiers</h2>
              <p className="text-muted-foreground text-lg max-w-2xl mx-auto">Unlock more benefits as you climb the ranks</p>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
              {tiers.map((tier) => (
                <Card
                  key={tier.name}
                  className={cn("relative overflow-hidden transition-all hover:scale-105", tier.name === currentTier && "ring-2 ring-primary")}
                >
                  <div className={cn("absolute top-0 left-0 right-0 h-24 bg-linear-to-br", tier.color)} />
                  <CardContent className="pt-16 pb-6 relative">
                    <div className="absolute top-8 left-1/2 -translate-x-1/2 w-16 h-16 rounded-full bg-white shadow-lg flex items-center justify-center">
                      <tier.icon className="w-8 h-8 text-foreground" />
                    </div>
                    <div className="text-center mt-8">
                      <h3 className="font-serif text-xl font-bold mb-1">{tier.name}</h3>
                      <p className="text-sm text-muted-foreground mb-4">
                        {tier.pointsRequired === 0 ? "Starting tier" : `${tier.pointsRequired.toLocaleString()} points`}
                      </p>
                      <ul className="space-y-2 text-left">
                        {tier.benefits.map((benefit) => (
                          <li key={benefit} className="flex items-start gap-2 text-sm">
                            <Check className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                            <span>{benefit}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </CardContent>
                  {tier.name === currentTier && (
                    <div className="absolute top-2 right-2 px-2 py-1 bg-primary text-primary-foreground text-xs font-semibold rounded">
                      Current
                    </div>
                  )}
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Available Rewards */}
        <section className="py-16">
          <div className="container mx-auto px-4">
            <div className="text-center mb-12">
              <h2 className="font-serif text-3xl md:text-4xl font-bold text-foreground mb-4">Redeem Your Points</h2>
              <p className="text-muted-foreground text-lg max-w-2xl mx-auto">Choose from a variety of delicious rewards</p>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl mx-auto">
              {rewards.map((reward) => (
                <Card key={reward.name} className="overflow-hidden group hover:shadow-lg transition-all">
                  <div className="aspect-4/3 relative overflow-hidden">
                    <img
                      src={reward.image}
                      alt={reward.name}
                      className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                    />
                    <div className="absolute inset-0 bg-linear-to-t from-black/60 to-transparent" />
                    <div className="absolute bottom-4 left-4 right-4">
                      <h3 className="font-semibold text-white text-lg">{reward.name}</h3>
                    </div>
                  </div>
                  <CardContent className="py-4 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Star className="w-5 h-5 text-secondary fill-secondary" />
                      <span className="font-bold text-lg">{reward.points}</span>
                      <span className="text-muted-foreground">points</span>
                    </div>
                    <Button
                      size="sm"
                      variant={currentPoints >= reward.points ? "default" : "outline"}
                      disabled={currentPoints < reward.points}
                      asChild={currentPoints >= reward.points}
                    >
                      {currentPoints >= reward.points ? (
                        <Link to="/checkout">Redeem at Checkout</Link>
                      ) : (
                        <span>Need {reward.points - currentPoints} more</span>
                      )}
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-16 bg-accent text-accent-foreground">
          <div className="container mx-auto px-4 text-center">
            <Percent className="w-16 h-16 mx-auto mb-6 text-secondary" />
            <h2 className="font-serif text-3xl md:text-4xl font-bold mb-4 text-balance">Start Earning Today</h2>
            <p className="text-lg text-accent-foreground/80 mb-8 max-w-2xl mx-auto">
              Join thousands of foodies who are already saving with Flavor Rewards. Sign up is free and takes just seconds.
            </p>
            {user ? (
              <Button size="lg" variant="secondary" className="font-semibold" asChild>
                <Link to="/points">View My Points</Link>
              </Button>
            ) : (
              <Button size="lg" variant="secondary" className="font-semibold" asChild>
                <Link to="/login">Create Free Account</Link>
              </Button>
            )}
          </div>
        </section>
      </main>
      <Footer />
    </div>
  )
}
