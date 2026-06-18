type EventProperties = Record<string, unknown>

type TrackOptions = {
  itemId?: number
  categoryId?: string
  cartId?: string
  orderId?: string
  experimentId?: string
  variantId?: string
  missionId?: string
  properties?: EventProperties
  consentState?: "unknown" | "essential" | "analytics_granted" | "analytics_denied"
}

const VISITOR_KEY = "order_visitor_id"
const SESSION_KEY = "order_session_id"
const ATTRIBUTION_KEY = "order_attribution"
const CART_KEY = "order_cart_id"
const MAX_QUEUE = 20

let queue: Array<Record<string, unknown>> = []
let flushTimer: number | null = null

const newId = (prefix: string) => `${prefix}_${crypto.randomUUID()}`

function getStorageId(storage: Storage, key: string, prefix: string): string {
  const existing = storage.getItem(key)
  if (existing) return existing
  const created = newId(prefix)
  storage.setItem(key, created)
  return created
}

export const getVisitorId = () => getStorageId(localStorage, VISITOR_KEY, "v")
export const getSessionId = () => getStorageId(sessionStorage, SESSION_KEY, "s")
export const getCartId = () => getStorageId(localStorage, CART_KEY, "c")
export const resetCartId = () => localStorage.setItem(CART_KEY, newId("c"))

function getAttribution() {
  const existing = sessionStorage.getItem(ATTRIBUTION_KEY)
  if (existing) return JSON.parse(existing)
  const params = new URLSearchParams(window.location.search)
  const referrer = document.referrer || ""
  let source = params.get("utm_source") || ""
  let medium = params.get("utm_medium") || ""
  if (!source && referrer) {
    try {
      source = new URL(referrer).hostname
      medium = "referral"
    } catch {
      source = "(direct)"
      medium = "(none)"
    }
  }
  if (!source) source = "(direct)"
  if (!medium) medium = "(none)"
  const attribution = {
    source,
    medium,
    campaign: params.get("utm_campaign") || undefined,
    content: params.get("utm_content") || undefined,
    term: params.get("utm_term") || undefined,
    clickId: params.get("gclid") || params.get("fbclid") || params.get("msclkid") || undefined,
  }
  sessionStorage.setItem(ATTRIBUTION_KEY, JSON.stringify(attribution))
  return attribution
}

function deviceClass() {
  const width = window.innerWidth
  return width < 768 ? "mobile" : width < 1024 ? "tablet" : "desktop"
}

export function track(eventName: string, options: TrackOptions = {}) {
  const attribution = getAttribution()
  const returningVisitor = Boolean(localStorage.getItem(VISITOR_KEY))
  const visitorId = getVisitorId()
  queue.push({
    eventId: crypto.randomUUID(),
    eventName,
    visitorId,
    sessionId: getSessionId(),
    occurredAt: new Date().toISOString(),
    pagePath: `${window.location.pathname}${window.location.search}`,
    referrer: document.referrer || undefined,
    ...attribution,
    itemId: options.itemId,
    categoryId: options.categoryId,
    cartId: options.cartId,
    orderId: options.orderId,
    experimentId: options.experimentId,
    variantId: options.variantId,
    missionId: options.missionId,
    properties: {
      deviceClass: deviceClass(),
      returningVisitor,
      ...options.properties,
    },
    schemaVersion: 1,
    consentState: options.consentState || "unknown",
  })
  if (queue.length >= MAX_QUEUE) void flushEvents()
  else if (flushTimer === null) flushTimer = window.setTimeout(() => void flushEvents(), 2000)
}

export async function flushEvents() {
  if (flushTimer !== null) window.clearTimeout(flushTimer)
  flushTimer = null
  if (!queue.length) return
  const batch = queue.splice(0, MAX_QUEUE)
  try {
    const response = await fetch("/api/v1/events/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: batch }),
      keepalive: true,
    })
    if (!response.ok && response.status >= 500) queue = batch.concat(queue).slice(0, 100)
  } catch {
    queue = batch.concat(queue).slice(0, 100)
  }
}

export function initializeAnalytics() {
  getVisitorId()
  getSessionId()
  getCartId()
  window.addEventListener("pagehide", () => void flushEvents())
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") void flushEvents()
  })
}
