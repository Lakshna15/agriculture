import type { RouteObject } from 'react-router'
import RedirectAuthenticated from './auth/RedirectAuthenticated.tsx'
import RequireRole from './auth/RequireRole.tsx'
import AppLayout from './components/AppLayout.tsx'
import CustomerReservationsPage from './pages/customer/CustomerReservationsPage.tsx'
import ExperiencesPage from './pages/customer/ExperiencesPage.tsx'
import ProductSearchPage from './pages/customer/ProductSearchPage.tsx'
import CustomerDashboardPage from './pages/CustomerDashboardPage.tsx'
import FarmEventsPage from './pages/farmer/FarmEventsPage.tsx'
import FarmPage from './pages/farmer/FarmPage.tsx'
import FarmReservationsPage from './pages/farmer/FarmReservationsPage.tsx'
import FarmerDashboardPage from './pages/FarmerDashboardPage.tsx'
import HomePage from './pages/HomePage.tsx'
import LoginPage from './pages/LoginPage.tsx'
import NotFoundPage from './pages/NotFoundPage.tsx'
import RegisterPage from './pages/RegisterPage.tsx'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      {
        path: 'login',
        element: (
          <RedirectAuthenticated>
            <LoginPage />
          </RedirectAuthenticated>
        ),
      },
      {
        path: 'register',
        element: (
          <RedirectAuthenticated>
            <RegisterPage />
          </RedirectAuthenticated>
        ),
      },
      {
        // The role check wraps the dashboard frame, so it covers every page inside it.
        path: 'customer',
        element: (
          <RequireRole role="CUSTOMER">
            <CustomerDashboardPage />
          </RequireRole>
        ),
        children: [
          { index: true, element: <ProductSearchPage /> },
          { path: 'experiences', element: <ExperiencesPage /> },
          { path: 'reservations', element: <CustomerReservationsPage /> },
        ],
      },
      {
        path: 'farmer',
        element: (
          <RequireRole role="FARMER">
            <FarmerDashboardPage />
          </RequireRole>
        ),
        children: [
          { index: true, element: <FarmPage /> },
          { path: 'events', element: <FarmEventsPage /> },
          { path: 'reservations', element: <FarmReservationsPage /> },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
