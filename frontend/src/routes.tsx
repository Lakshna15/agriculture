import type { RouteObject } from 'react-router'
import RedirectAuthenticated from './auth/RedirectAuthenticated.tsx'
import RequireRole from './auth/RequireRole.tsx'
import RequireSignedIn from './auth/RequireSignedIn.tsx'
import AppLayout from './components/AppLayout.tsx'
import CropJourneyPage from './pages/CropJourneyPage.tsx'
import CropPollsPage from './pages/customer/CropPollsPage.tsx'
import CropRequestsPage from './pages/customer/CropRequestsPage.tsx'
import CustomerReservationsPage from './pages/customer/CustomerReservationsPage.tsx'
import ExperiencesPage from './pages/customer/ExperiencesPage.tsx'
import GrowOffersPage from './pages/customer/GrowOffersPage.tsx'
import ProductSearchPage from './pages/customer/ProductSearchPage.tsx'
import CustomerDashboardPage from './pages/CustomerDashboardPage.tsx'
import FarmCropPollsPage from './pages/farmer/FarmCropPollsPage.tsx'
import FarmEventsPage from './pages/farmer/FarmEventsPage.tsx'
import FarmPage from './pages/farmer/FarmPage.tsx'
import FarmReservationsPage from './pages/farmer/FarmReservationsPage.tsx'
import GrowOnDemandPage from './pages/farmer/GrowOnDemandPage.tsx'
import FarmerDashboardPage from './pages/FarmerDashboardPage.tsx'
import HomePage from './pages/HomePage.tsx'
import LoginPage from './pages/LoginPage.tsx'
import NotFoundPage from './pages/NotFoundPage.tsx'
import NotificationsPage from './pages/NotificationsPage.tsx'
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
          { path: 'crop-requests', element: <CropRequestsPage /> },
          { path: 'grow-offers', element: <GrowOffersPage /> },
          { path: 'grow-offers/:offerId', element: <CropJourneyPage audience="customer" /> },
          { path: 'crop-polls', element: <CropPollsPage /> },
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
          { path: 'grow-on-demand', element: <GrowOnDemandPage /> },
          { path: 'grow-on-demand/:offerId', element: <CropJourneyPage audience="farmer" /> },
          { path: 'crop-polls', element: <FarmCropPollsPage /> },
          { path: 'reservations', element: <FarmReservationsPage /> },
        ],
      },
      {
        path: 'notifications',
        element: (
          <RequireSignedIn>
            <NotificationsPage />
          </RequireSignedIn>
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
