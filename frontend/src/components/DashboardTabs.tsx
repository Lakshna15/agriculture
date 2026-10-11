import { NavLink } from 'react-router'

type DashboardTab = {
  to: string
  label: string
  /** True for the tab at the dashboard's own path, so it is not active on its sub-pages. */
  end?: boolean
}

function tabClassName({ isActive }: { isActive: boolean }) {
  const base =
    '-mb-px border-b-2 px-1 pb-3 text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-700'
  return isActive
    ? `${base} border-green-700 text-green-800`
    : `${base} border-transparent text-stone-600 hover:border-stone-300 hover:text-stone-900`
}

export default function DashboardTabs({ label, tabs }: { label: string; tabs: DashboardTab[] }) {
  return (
    <nav aria-label={label} className="mt-6 flex gap-6 overflow-x-auto border-b border-stone-200">
      {tabs.map((tab) => (
        <NavLink key={tab.to} to={tab.to} end={tab.end} className={tabClassName}>
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}
