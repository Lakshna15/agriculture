import type { ReactNode } from 'react'
import { Navigate } from 'react-router'
import { useAuth } from './useAuth.ts'

/**
 * Keeps a page for signed-in users of any role. Like RequireRole, this is a
 * navigation convenience: the API checks the token on every request.
 */
export default function RequireSignedIn({ children }: { children: ReactNode }) {
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
  return children
}
