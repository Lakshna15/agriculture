import type { RouteObject } from 'react-router'
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
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'customer', element: <CustomerDashboardPage /> },
      { path: 'farmer', element: <FarmerDashboardPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
