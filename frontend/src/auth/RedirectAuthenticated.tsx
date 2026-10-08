import type { ReactNode } from 'react'
import { Navigate } from 'react-router'
import { dashboardPathForRole } from './roles.ts'
import { useAuth } from './useAuth.ts'

/**
 * Wraps the login and register pages. A signed-in user is sent to the
 * dashboard for their role, which is also what moves them on after the form
 * succeeds.
 */
export default function RedirectAuthenticated({ children }: { children: ReactNode }) {
  const auth = useAuth()

  if (auth.status === 'authenticated') {
    return <Navigate to={dashboardPathForRole(auth.user.role)} replace />
  }
  return children
}
