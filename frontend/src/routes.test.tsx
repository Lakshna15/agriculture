import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { installFakeApi } from './test/fakeApi.ts'
import { renderApp } from './test/renderApp.tsx'

describe('public routes', () => {
  beforeEach(() => {
    installFakeApi()
  })

  it('shows the product name and description on the homepage', () => {
    renderApp('/')

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
    ['/does-not-exist', 'Page not found'],
  ])('renders %s with the "%s" heading', (path, heading) => {
    renderApp(path)

    expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })

  it('navigates from the homepage to login and register through the header', async () => {
    const user = userEvent.setup()
    renderApp('/')
    const accountNavigation = screen.getByRole('navigation', { name: 'Account' })

    await user.click(within(accountNavigation).getByRole('link', { name: 'Login' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Login' })).toBeInTheDocument()

    await user.click(within(accountNavigation).getByRole('link', { name: 'Register' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Register' })).toBeInTheDocument()
  })
})
