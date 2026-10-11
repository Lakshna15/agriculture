import { Outlet } from 'react-router'
import DashboardTabs from '../components/DashboardTabs.tsx'

const farmerTabs = [
  { to: '/farmer', label: 'Farm and products', end: true },
  { to: '/farmer/events', label: 'Farm events' },
  { to: '/farmer/reservations', label: 'Reservations' },
]

/** Frame shared by every farmer page: the heading and the section tabs. */
export default function FarmerDashboardPage() {
  return (
    <>
      <h1 className="text-3xl font-bold tracking-tight text-stone-900">Farmer Dashboard</h1>
      <p className="mt-2 text-stone-600">
        Manage your farm, what you sell, the experiences you host and your reservations.
      </p>
      <DashboardTabs label="Farmer dashboard sections" tabs={farmerTabs} />
      <div className="mt-8">
        <Outlet />
      </div>
    </>
  )
}
