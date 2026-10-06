import { Link, NavLink, Outlet } from 'react-router'

function navLinkClassName({ isActive }: { isActive: boolean }) {
  const base =
    'rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-700'
  return isActive
    ? `${base} bg-green-100 text-green-900`
    : `${base} text-stone-700 hover:bg-stone-100 hover:text-stone-900`
}

export default function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-stone-50 text-stone-900">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
          <Link
            to="/"
            className="rounded-md text-lg font-semibold tracking-tight text-green-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-700"
          >
            Farm2Local
          </Link>
          <nav aria-label="Account" className="flex items-center gap-1">
            <NavLink to="/login" className={navLinkClassName}>
              Login
            </NavLink>
            <NavLink to="/register" className={navLinkClassName}>
              Register
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6 sm:py-16">
        <Outlet />
      </main>
    </div>
  )
}
