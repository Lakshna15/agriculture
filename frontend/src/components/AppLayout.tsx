import { Link, NavLink, Outlet } from 'react-router'
import { dashboardPathForRole } from '../auth/roles.ts'
import { useAuth } from '../auth/useAuth.ts'

const navItemClassName =
  'rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-700'
const inactiveNavItemClassName = `${navItemClassName} text-stone-700 hover:bg-stone-100 hover:text-stone-900`

function navLinkClassName({ isActive }: { isActive: boolean }) {
  return isActive ? `${navItemClassName} bg-green-100 text-green-900` : inactiveNavItemClassName
}

export default function AppLayout() {
  const auth = useAuth()

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
        <Outlet />
      </main>
    </div>
  )
}
