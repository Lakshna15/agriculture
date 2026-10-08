import type { ReactNode } from 'react'
import { Navigate } from 'react-router'
import type { UserRole } from '../api/auth.ts'
import { dashboardPathForRole } from './roles.ts'
import { useAuth } from './useAuth.ts'

type RequireRoleProps = {
  role: UserRole
  children: ReactNode
}

/**
 * Keeps a page for one role. This is a navigation convenience only: the API
 * enforces the same rule on every request.
 */
export default function RequireRole({ role, children }: RequireRoleProps) {
  const auth = useAuth()

  if (auth.status === 'loading') {
    return (
      <p role="status" className="text-center text-stone-600">
        Loading your account…
      </p>
    )
  }
  if (auth.status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }
  if (auth.user.role !== role) {
    return <Navigate to={dashboardPathForRole(auth.user.role)} replace />
  }
  return children
}
