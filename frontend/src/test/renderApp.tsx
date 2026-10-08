import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import AuthProvider from '../auth/AuthProvider.tsx'
import { routes } from '../routes.tsx'

/** Renders the whole application, as main.tsx does, starting at the given path. */
export function renderApp(initialPath: string) {
  const router = createMemoryRouter(routes, { initialEntries: [initialPath] })
  render(
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>,
  )
  return router
}
