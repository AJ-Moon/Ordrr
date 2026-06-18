import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react"
import { getCartId, getSessionId, getVisitorId, resetCartId, track } from "@/lib/analytics"

export interface CartItem {
  menuItemId: number
  name: string
  price: number
  image: string
  quantity: number
}

interface CartContextType {
  items: CartItem[]
  addItem: (item: Omit<CartItem, "quantity">, qty?: number) => void
  removeItem: (menuItemId: number) => void
  updateQty: (menuItemId: number, qty: number) => void
  clearCart: () => void
  total: number
  count: number
}

const CART_KEY = "flavor_hub_cart"

const CartContext = createContext<CartContextType | null>(null)

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>(() => {
    try {
      const stored = localStorage.getItem(CART_KEY)
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  })

  const syncCart = useCallback((cartItems: CartItem[], cartId = getCartId()) => {
    const token = localStorage.getItem("auth_token")
    return fetch("/api/v1/carts/sync", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        cartId,
        visitorId: getVisitorId(),
        sessionId: getSessionId(),
        items: cartItems.map((item) => ({ menuItemId: item.menuItemId, quantity: item.quantity })),
      }),
    }).catch(() => undefined)
  }, [])

  useEffect(() => {
    localStorage.setItem(CART_KEY, JSON.stringify(items))
    if (!items.length) return
    const timer = window.setTimeout(() => {
      void syncCart(items)
    }, 400)
    return () => window.clearTimeout(timer)
  }, [items, syncCart])

  const addItem = useCallback((item: Omit<CartItem, "quantity">, qty = 1) => {
    track("item_added_to_cart", {
      itemId: item.menuItemId,
      cartId: getCartId(),
      properties: { quantity: qty, displayedPrice: item.price },
    })
    setItems((prev) => {
      const existing = prev.find((i) => i.menuItemId === item.menuItemId)
      if (existing) {
        return prev.map((i) =>
          i.menuItemId === item.menuItemId ? { ...i, quantity: i.quantity + qty } : i
        )
      }
      return [...prev, { ...item, quantity: qty }]
    })
  }, [])

  const removeItem = useCallback((menuItemId: number) => {
    track("item_removed_from_cart", { itemId: menuItemId, cartId: getCartId() })
    setItems((prev) => prev.filter((i) => i.menuItemId !== menuItemId))
  }, [])

  const updateQty = useCallback((menuItemId: number, qty: number) => {
    track(qty <= 0 ? "item_removed_from_cart" : "cart_value_changed", {
      itemId: menuItemId,
      cartId: getCartId(),
      properties: { quantity: qty },
    })
    if (qty <= 0) {
      setItems((prev) => prev.filter((i) => i.menuItemId !== menuItemId))
    } else {
      setItems((prev) =>
        prev.map((i) => (i.menuItemId === menuItemId ? { ...i, quantity: qty } : i))
      )
    }
  }, [])

  const clearCart = useCallback(() => {
    const previousCartId = getCartId()
    setItems([])
    void syncCart([], previousCartId)
    resetCartId()
  }, [syncCart])

  const total = items.reduce((sum, i) => sum + i.price * i.quantity, 0)
  const count = items.reduce((sum, i) => sum + i.quantity, 0)

  return (
    <CartContext.Provider value={{ items, addItem, removeItem, updateQty, clearCart, total, count }}>
      {children}
    </CartContext.Provider>
  )
}

export function useCart() {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error("useCart must be used within CartProvider")
  return ctx
}
