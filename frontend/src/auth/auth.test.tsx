import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { buildUser, installFakeApi } from '../test/fakeApi.ts'
import { renderApp } from '../test/renderApp.tsx'

const ACCESS_TOKEN_STORAGE_KEY = 'farm2local.accessToken'

const customer = buildUser({ id: 1, name: 'Ana Grower', email: 'ana@example.com', role: 'CUSTOMER' })
const farmer = buildUser({ id: 2, name: 'Ben Fields', email: 'ben@example.com', role: 'FARMER' })
const customerAccount = { user: customer, password: 'correct-horse-battery' }
const farmerAccount = { user: farmer, password: 'tractor-barn-orchard' }

function dashboardHeading(name: 'Customer Dashboard' | 'Farmer Dashboard') {
  return screen.findByRole('heading', { level: 1, name })
}

async function submitLoginForm(email: string, password: string) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Login' }))
}

describe('registration', () => {
  it('creates a farmer account, signs in and opens the farmer dashboard', async () => {
    const api = installFakeApi()
    const user = userEvent.setup()
    renderApp('/register')

    await user.type(screen.getByLabelText('Name'), 'Ben Fields')
    await user.type(screen.getByLabelText('Email'), 'ben@example.com')
    await user.type(screen.getByLabelText('Password'), 'tractor-barn-orchard')
    await user.click(screen.getByRole('radio', { name: /Farmer/ }))
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await dashboardHeading('Farmer Dashboard')).toBeInTheDocument()
    expect(api.requests[0]).toEqual({
      method: 'POST',
      path: '/api/auth/register',
      body: {
        name: 'Ben Fields',
        email: 'ben@example.com',
        password: 'tractor-barn-orchard',
        role: 'FARMER',
      },
    })
  })

  it('registers a customer by default and opens the customer dashboard', async () => {
    installFakeApi()
    const user = userEvent.setup()
    renderApp('/register')

    expect(screen.getByRole('radio', { name: /Customer/ })).toBeChecked()
    await user.type(screen.getByLabelText('Name'), 'Ana Grower')
    await user.type(screen.getByLabelText('Email'), 'ana@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await dashboardHeading('Customer Dashboard')).toBeInTheDocument()
  })

  it('offers only the customer and farmer roles', () => {
    installFakeApi()
    renderApp('/register')

    const roleNames = screen.getAllByRole('radio').map((radio) => (radio as HTMLInputElement).value)
    expect(roleNames).toEqual(['CUSTOMER', 'FARMER'])
  })

  it('shows the server message when the email is already registered', async () => {
    installFakeApi({ accounts: [customerAccount] })
    const user = userEvent.setup()
    renderApp('/register')

    await user.type(screen.getByLabelText('Name'), 'Another Ana')
    await user.type(screen.getByLabelText('Email'), 'ana@example.com')
    await user.type(screen.getByLabelText('Password'), 'a-different-password')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'An account with this email already exists',
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Register' })).toBeInTheDocument()
    expect(window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)).toBeNull()
  })
})

describe('login', () => {
  it('sends a customer to the customer dashboard', async () => {
    installFakeApi({ accounts: [customerAccount, farmerAccount] })
    renderApp('/login')

    await submitLoginForm('ana@example.com', 'correct-horse-battery')

    expect(await dashboardHeading('Customer Dashboard')).toBeInTheDocument()
  })

  it('sends a farmer to the farmer dashboard', async () => {
    installFakeApi({ accounts: [customerAccount, farmerAccount] })
    renderApp('/login')

    await submitLoginForm('ben@example.com', 'tractor-barn-orchard')

    expect(await dashboardHeading('Farmer Dashboard')).toBeInTheDocument()
  })

  it('shows an error and stays on the page when the password is wrong', async () => {
    installFakeApi({ accounts: [customerAccount] })
    renderApp('/login')

    await submitLoginForm('ana@example.com', 'not-the-password')

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password')
    expect(screen.getByRole('heading', { level: 1, name: 'Login' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Login' })).toBeEnabled()
    expect(window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)).toBeNull()
  })

  it('shows the signed-in user and replaces the login links in the header', async () => {
    installFakeApi({ accounts: [customerAccount] })
    renderApp('/login')

    await submitLoginForm('ana@example.com', 'correct-horse-battery')
    await dashboardHeading('Customer Dashboard')

    const accountNavigation = screen.getByRole('navigation', { name: 'Account' })
    expect(within(accountNavigation).getByText('Ana Grower')).toBeInTheDocument()
    expect(within(accountNavigation).getByRole('button', { name: 'Logout' })).toBeInTheDocument()
    expect(within(accountNavigation).queryByRole('link', { name: 'Login' })).not.toBeInTheDocument()
  })
})

describe('session', () => {
  it('restores the session from a stored token after a page load', async () => {
    const api = installFakeApi({ accounts: [farmerAccount] })
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, api.issueToken(farmer))

    renderApp('/farmer')

    expect(screen.getByRole('status')).toHaveTextContent('Loading your account')
    expect(await dashboardHeading('Farmer Dashboard')).toBeInTheDocument()
  })

  it('discards a stored token the server no longer accepts', async () => {
    installFakeApi({ accounts: [farmerAccount] })
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, 'expired-token')

    renderApp('/farmer')

    expect(await screen.findByRole('heading', { level: 1, name: 'Login' })).toBeInTheDocument()
    expect(window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)).toBeNull()
  })

  it('signs out, clears the token and returns to the login page', async () => {
    const api = installFakeApi({ accounts: [customerAccount] })
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, api.issueToken(customer))
    const user = userEvent.setup()
    renderApp('/customer')
    await dashboardHeading('Customer Dashboard')

    await user.click(screen.getByRole('button', { name: 'Logout' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Login' })).toBeInTheDocument()
    expect(window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)).toBeNull()
  })
})

describe('dashboard access', () => {
  it.each(['/customer', '/farmer'])('sends a visitor from %s to the login page', async (path) => {
    installFakeApi()

    renderApp(path)

    expect(await screen.findByRole('heading', { level: 1, name: 'Login' })).toBeInTheDocument()
  })

  it('sends a farmer who opens the customer dashboard to the farmer dashboard', async () => {
    const api = installFakeApi({ accounts: [farmerAccount] })
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, api.issueToken(farmer))

    renderApp('/customer')

    expect(await dashboardHeading('Farmer Dashboard')).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { level: 1, name: 'Customer Dashboard' }),
    ).not.toBeInTheDocument()
  })

  it('sends a customer who opens the farmer dashboard to the customer dashboard', async () => {
    const api = installFakeApi({ accounts: [customerAccount] })
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, api.issueToken(customer))

    renderApp('/farmer')

    expect(await dashboardHeading('Customer Dashboard')).toBeInTheDocument()
  })

  it('sends a signed-in user who opens the login page to their dashboard', async () => {
    const api = installFakeApi({ accounts: [customerAccount] })
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, api.issueToken(customer))

    renderApp('/login')

    expect(await dashboardHeading('Customer Dashboard')).toBeInTheDocument()
  })
})
