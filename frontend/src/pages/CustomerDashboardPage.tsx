import { Outlet } from 'react-router'
import DashboardTabs from '../components/DashboardTabs.tsx'

const customerTabs = [
  { to: '/customer', label: 'Products', end: true },
  { to: '/customer/experiences', label: 'Farm experiences' },
  { to: '/customer/reservations', label: 'My reservations' },
]

/** Frame shared by every customer page: the heading and the section tabs. */
export default function CustomerDashboardPage() {
  return (
    <>
      <h1 className="text-3xl font-bold tracking-tight text-stone-900">Customer Dashboard</h1>
      <p className="mt-2 text-stone-600">
        Find fresh products and farm experiences near you, and keep track of what you reserved.
      </p>
      <DashboardTabs label="Customer dashboard sections" tabs={customerTabs} />
      <div className="mt-8">
        <Outlet />
      </div>
    </>
  )
}
