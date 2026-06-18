import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  Menu,
  ShoppingCart,
  User,
  MapPin,
  Phone,
  UtensilsCrossed,
  Truck,
  Star,
  History,
  LogOut,
  ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AnnouncementBar } from "@/components/AnnouncementBar";
import { useAuth } from "@/contexts/AuthContext";
import { useCart } from "@/contexts/CartContext";
import { useRestaurant } from "@/contexts/RestaurantContext";

const publicNavLinks = [
  { href: "/menu", label: "Explore Menu", icon: UtensilsCrossed },
  { href: "/order-architect", label: "Order Architect", icon: Star },
  { href: "/concepts", label: "Product Lab", icon: Star },
  { href: "/track", label: "Track Order", icon: Truck },
  { href: "/branches", label: "Branch Locator", icon: MapPin },
  { href: "/contact", label: "Contact Us", icon: Phone },
];

const authNavLinks = [
  { href: "/points", label: "Points & Rewards", icon: Star },
  { href: "/history", label: "Previous Orders", icon: History },
];

export function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { user, logout } = useAuth();
  const { count } = useCart();
  const navigate = useNavigate();
  const { restaurantName, logoUrl, primaryColor, restaurantOpen, closedMessage } =
    useRestaurant();
  const isRestaurantClosed = restaurantOpen === "false";

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/");
    setIsOpen(false);
  };

  const allDesktopLinks = user
    ? [
        ...publicNavLinks.slice(0, 1),
        ...authNavLinks,
        ...publicNavLinks.slice(1),
      ]
    : publicNavLinks;

  return (
    <>
      {/* Desktop & Tablet Navbar */}
      <header
        className={cn(
          "sticky top-0 z-50 w-full border-b transition-all duration-300",
          scrolled
            ? "border-border/40 bg-background/95 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/90"
            : "border-transparent bg-transparent",
        )}
      >
        <AnnouncementBar />
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 lg:px-8">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2">
            {logoUrl ? (
              <div className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg border bg-background">
                <img
                  src={logoUrl}
                  alt={`${restaurantName} logo`}
                  className="h-full w-full object-contain"
                />
              </div>
            ) : (
              <div
                className="flex h-9 w-9 items-center justify-center rounded-lg"
                style={{ backgroundColor: primaryColor }}
              >
                <UtensilsCrossed className="h-5 w-5 text-white" />
              </div>
            )}
            <span className="font-serif text-xl font-bold tracking-tight text-foreground">
              {restaurantName}
            </span>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden items-center gap-1 md:flex">
            {allDesktopLinks.map((link) => (
              <Link
                key={link.href}
                to={link.href}
                className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                {link.label}
              </Link>
            ))}
          </nav>

          {/* Right Actions */}
          <div className="flex items-center gap-2">
            {/* Cart Button */}
            <Button variant="ghost" size="icon" className="relative" asChild>
              <Link to="/cart">
                <ShoppingCart className="h-5 w-5" />
                {count > 0 && (
                  <Badge className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-primary p-0 text-xs text-primary-foreground">
                    {count}
                  </Badge>
                )}
                <span className="sr-only">Shopping cart</span>
              </Link>
            </Button>

            {/* Auth Buttons - Desktop */}
            {user ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    className="hidden sm:inline-flex gap-2"
                  >
                    <User className="h-4 w-4" />
                    {user.firstName}
                    <ChevronDown className="h-3 w-3" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem asChild>
                    <Link to="/profile">My Profile</Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/history">Previous Orders</Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/points">Points & Rewards</Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={handleLogout}
                    className="text-destructive"
                  >
                    <LogOut className="mr-2 h-4 w-4" />
                    Sign Out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <Button
                asChild
                variant="outline"
                className="hidden sm:inline-flex"
                style={{ borderColor: primaryColor, color: primaryColor }}
              >
                <Link to="/login">
                  <User className="mr-2 h-4 w-4" />
                  Login
                </Link>
              </Button>
            )}

            {/* Mobile Menu */}
            <Sheet open={isOpen} onOpenChange={setIsOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden">
                  <Menu className="h-5 w-5" />
                  <span className="sr-only">Toggle menu</span>
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-[300px] sm:w-[350px]">
                <nav className="flex flex-col gap-1 pt-8">
                  {publicNavLinks.map((link) => {
                    const Icon = link.icon;
                    return (
                      <Link
                        key={link.href}
                        to={link.href}
                        onClick={() => setIsOpen(false)}
                        className="flex items-center gap-3 rounded-lg px-3 py-3 text-base font-medium text-foreground transition-colors hover:bg-accent"
                      >
                        <Icon className="h-5 w-5 text-primary" />
                        {link.label}
                      </Link>
                    );
                  })}
                  {user &&
                    authNavLinks.map((link) => {
                      const Icon = link.icon;
                      return (
                        <Link
                          key={link.href}
                          to={link.href}
                          onClick={() => setIsOpen(false)}
                          className="flex items-center gap-3 rounded-lg px-3 py-3 text-base font-medium text-foreground transition-colors hover:bg-accent"
                        >
                          <Icon className="h-5 w-5 text-primary" />
                          {link.label}
                        </Link>
                      );
                    })}
                  <hr className="my-2 border-border" />
                  {user ? (
                    <>
                      <Link
                        to="/profile"
                        onClick={() => setIsOpen(false)}
                        className="flex items-center gap-3 rounded-lg px-3 py-3 text-base font-medium text-foreground transition-colors hover:bg-accent"
                      >
                        <User className="h-5 w-5 text-primary" />
                        {user.firstName} {user.lastName}
                      </Link>
                      <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 rounded-lg px-3 py-3 text-base font-medium text-destructive transition-colors hover:bg-destructive/10 w-full"
                      >
                        <LogOut className="h-5 w-5" />
                        Sign Out
                      </button>
                    </>
                  ) : (
                    <Link
                      to="/login"
                      onClick={() => setIsOpen(false)}
                      className="flex items-center gap-3 rounded-lg px-3 py-3 text-base font-medium text-foreground transition-colors hover:bg-accent"
                    >
                      <User className="h-5 w-5 text-primary" />
                      Login / Sign Up
                    </Link>
                  )}
                </nav>
              </SheetContent>
            </Sheet>
          </div>
        </div>

        {isRestaurantClosed && (
          <div className="w-full bg-red-600 text-white">
            <div className="mx-auto max-w-7xl px-4 py-2 text-center text-sm font-medium lg:px-8">
              {closedMessage}
            </div>
          </div>
        )}
      </header>

      {/* Mobile Bottom Navigation Bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 md:hidden">
        <div className="flex h-16 items-center justify-around">
          <Link
            to="/menu"
            className="flex flex-1 flex-col items-center justify-center gap-1 py-2 text-muted-foreground transition-colors hover:text-primary"
          >
            <UtensilsCrossed className="h-5 w-5" />
            <span className="text-xs font-medium">Menu</span>
          </Link>
          <Link
            to="/cart"
            className="relative flex flex-1 flex-col items-center justify-center gap-1 py-2 text-muted-foreground transition-colors hover:text-primary"
          >
            <div className="relative">
              <ShoppingCart className="h-5 w-5" />
              {count > 0 && (
                <span className="absolute -right-2 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                  {count}
                </span>
              )}
            </div>
            <span className="text-xs font-medium">Cart</span>
          </Link>
          <Link
            to="/track"
            className="flex flex-1 flex-col items-center justify-center gap-1 py-2 text-muted-foreground transition-colors hover:text-primary"
          >
            <Truck className="h-5 w-5" />
            <span className="text-xs font-medium">Track</span>
          </Link>
          <Link
            to={user ? "/profile" : "/login"}
            className="flex flex-1 flex-col items-center justify-center gap-1 py-2 text-muted-foreground transition-colors hover:text-primary"
          >
            <User className="h-5 w-5" />
            <span className="text-xs font-medium">
              {user ? user.firstName : "Login"}
            </span>
          </Link>
        </div>
      </nav>
    </>
  );
}
