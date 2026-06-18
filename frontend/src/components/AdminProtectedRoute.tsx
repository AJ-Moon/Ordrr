import { Navigate, Outlet } from "react-router-dom"

/** Decode a JWT payload without verifying the signature (backend verifies). */
function parseJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")
    return JSON.parse(atob(base64))
  } catch {
    return null
  }
}

export default function AdminProtectedRoute() {
  const token = localStorage.getItem("admin_token")

  if (!token) return <Navigate to="/admin/login" replace />

  const payload = parseJwtPayload(token)

  // Reject if payload is malformed, not an admin token, or expired
  if (
    !payload ||
    payload["type"] !== "admin" ||
    (typeof payload["exp"] === "number" && payload["exp"] < Date.now() / 1000)
  ) {
    localStorage.removeItem("admin_token")
    localStorage.removeItem("admin_user")
    return <Navigate to="/admin/login" replace />
  }

  return <Outlet />
}
