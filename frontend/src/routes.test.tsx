import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'
import { routes } from './routes.tsx'

function renderRoute(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<RouterProvider router={router} />)
}

describe('application routes', () => {
  it('shows the product name and description on the homepage', () => {
    renderRoute('/')

    expect(screen.getByRole('heading', { level: 1, name: 'Farm2Local' })).toBeInTheDocument()
    expect(
      screen.getByText(
        'A local agriculture marketplace connecting customers with nearby farms, fresh products and farm experiences.',
      ),
    ).toBeInTheDocument()
  })

  it.each([
    ['/login', 'Login'],
    ['/register', 'Register'],
    ['/customer', 'Customer Dashboard'],
    ['/farmer', 'Farmer Dashboard'],
  ])('renders %s with the "%s" heading', (path, heading) => {
    renderRoute(path)

    expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })

  it('shows a not-found page for an unknown path', () => {
    renderRoute('/does-not-exist')

    expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeInTheDocument()
  })

  it('navigates from the homepage to login and register through the header', async () => {
    const user = userEvent.setup()
    renderRoute('/')
    const accountNavigation = screen.getByRole('navigation', { name: 'Account' })

    await user.click(within(accountNavigation).getByRole('link', { name: 'Login' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Login' })).toBeInTheDocument()

    await user.click(within(accountNavigation).getByRole('link', { name: 'Register' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Register' })).toBeInTheDocument()
  })
})
