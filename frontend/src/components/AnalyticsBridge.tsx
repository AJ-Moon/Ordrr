import { useEffect } from "react"
import { useLocation } from "react-router-dom"
import { initializeAnalytics, track } from "@/lib/analytics"

let initialized = false

export function AnalyticsBridge() {
  const location = useLocation()

  useEffect(() => {
    if (!initialized) {
      initializeAnalytics()
      initialized = true
    }
  }, [])

  useEffect(() => {
    track("page_viewed", { properties: { title: document.title } })
  }, [location.pathname, location.search])

  return null
}
