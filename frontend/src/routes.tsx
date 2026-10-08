import type { RouteObject } from 'react-router'
import RedirectAuthenticated from './auth/RedirectAuthenticated.tsx'
import RequireRole from './auth/RequireRole.tsx'
import AppLayout from './components/AppLayout.tsx'
import CustomerDashboardPage from './pages/CustomerDashboardPage.tsx'
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
        path: 'customer',
        element: (
          <RequireRole role="CUSTOMER">
            <CustomerDashboardPage />
          </RequireRole>
        ),
      },
      {
        path: 'farmer',
        element: (
          <RequireRole role="FARMER">
            <FarmerDashboardPage />
          </RequireRole>
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
