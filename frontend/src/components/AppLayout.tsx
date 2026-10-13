import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { fetchUnreadNotificationCount } from '../api/notifications.ts'
import { dashboardPathForRole } from '../auth/roles.ts'
import { useAuth } from '../auth/useAuth.ts'

const navItemClassName =
  'rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-700'
const inactiveNavItemClassName = `${navItemClassName} text-stone-700 hover:bg-stone-100 hover:text-stone-900`

function navLinkClassName({ isActive }: { isActive: boolean }) {
  return isActive ? `${navItemClassName} bg-green-100 text-green-900` : inactiveNavItemClassName
}

/** What pages rendered inside the layout can ask of it, through the router's outlet context. */
export type AppLayoutContext = {
  /** Re-reads the unread count shown in the header, after a page changes it. */
  refreshUnreadNotificationCount: () => void
}

export default function AppLayout() {
  const auth = useAuth()
  const { pathname } = useLocation()
  const accessToken = auth.status === 'authenticated' ? auth.accessToken : null
  const [unreadCount, setUnreadCount] = useState(0)
  const [refreshNumber, setRefreshNumber] = useState(0)

  // The count is read again on every navigation, which keeps it reasonably
  // fresh without polling the server on a timer.
  useEffect(() => {
    if (accessToken === null) {
      return
    }
    let isCurrent = true
    fetchUnreadNotificationCount(accessToken)
      .then((count) => {
        if (isCurrent) {
          setUnreadCount(count)
        }
      })
      .catch(() => {
        // The badge is a convenience. A failure here must not disturb the page.
      })
    return () => {
      isCurrent = false
    }
  }, [accessToken, pathname, refreshNumber])

  const refreshUnreadNotificationCount = useCallback(() => {
    setRefreshNumber((current) => current + 1)
  }, [])

  const visibleUnreadCount = accessToken === null ? 0 : unreadCount

  return (
    <div className="flex min-h-screen flex-col bg-stone-50 text-stone-900">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link
            to="/"
            className="rounded-md text-lg font-semibold tracking-tight text-green-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-700"
          >
            Farm2Local
          </Link>
          <nav aria-label="Account" className="flex items-center gap-1">
            {auth.status === 'authenticated' && (
              <>
                <span className="hidden px-2 text-sm text-stone-600 sm:inline">
                  Signed in as <span className="font-medium text-stone-900">{auth.user.name}</span>
                </span>
                {auth.user.role !== 'ADMIN' && (
                  <NavLink to={dashboardPathForRole(auth.user.role)} className={navLinkClassName}>
                    Dashboard
                  </NavLink>
                )}
                <NavLink
                  to="/notifications"
                  className={navLinkClassName}
                  aria-label={
                    visibleUnreadCount > 0
                      ? `Notifications, ${visibleUnreadCount} unread`
                      : 'Notifications'
                  }
                >
                  Notifications
                  {visibleUnreadCount > 0 && (
                    <span className="ml-1.5 rounded-full bg-green-700 px-1.5 py-0.5 text-xs font-semibold text-white">
                      {visibleUnreadCount}
                    </span>
                  )}
                </NavLink>
                <button type="button" onClick={auth.logout} className={inactiveNavItemClassName}>
                  Logout
                </button>
              </>
            )}
            {auth.status === 'unauthenticated' && (
              <>
                <NavLink to="/login" className={navLinkClassName}>
                  Login
                </NavLink>
                <NavLink to="/register" className={navLinkClassName}>
                  Register
                </NavLink>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6 sm:py-16">
        <Outlet context={{ refreshUnreadNotificationCount } satisfies AppLayoutContext} />
      </main>
    </div>
  )
}
