import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Notification } from '../api/notifications.ts'
import { buildNotification, buildUser, installFakeApi } from '../test/fakeApi.ts'
import { renderApp } from '../test/renderApp.tsx'

const customer = buildUser({ id: 1, name: 'Ana Grower', email: 'ana@example.com', role: 'CUSTOMER' })
const farmer = buildUser({ id: 7, name: 'Ben Fields', email: 'ben@example.com', role: 'FARMER' })

const confirmed = buildNotification({ id: 1 })
const ready = buildNotification({
  id: 2,
  type: 'CROP_READY',
  message: 'Your Okra from Green Acres is ready.',
  created_at: '2026-07-01T14:00:00Z',
})
const alreadyRead = buildNotification({
  id: 3,
  type: 'CROP_UPDATE_POSTED',
  message: 'Green Acres posted an update: your Okra has been planted.',
  read: true,
})

function openApp(path: string, notifications: Notification[] = [], user = customer) {
  const api = installFakeApi({
    accounts: [{ user, password: 'correct-horse-battery' }],
    notifications,
  })
  api.signIn(user)
  renderApp(path)
  return api
}

async function findAccountNavigation() {
  await screen.findByRole('button', { name: 'Logout' })
  return within(screen.getByRole('navigation', { name: 'Account' }))
}

function findNotificationItem(message: string) {
  return within(screen.getByText(message).closest('li')!)
}

describe('unread badge in the header', () => {
  it('shows how many notifications are unread', async () => {
    openApp('/customer', [confirmed, ready, alreadyRead])
    const navigation = await findAccountNavigation()

    expect(
      await navigation.findByRole('link', { name: 'Notifications, 2 unread' }),
    ).toHaveTextContent('Notifications2')
  })

  it('shows no number when everything has been read', async () => {
    openApp('/customer', [alreadyRead])
    const navigation = await findAccountNavigation()

    expect(navigation.getByRole('link', { name: 'Notifications' })).toHaveTextContent(
      /^Notifications$/,
    )
  })

  it('is not shown to a visitor who is not signed in', () => {
    installFakeApi()
    renderApp('/')

    expect(screen.queryByRole('link', { name: /Notifications/ })).not.toBeInTheDocument()
  })
})

describe('notifications page', () => {
  it('lists notifications with the unread ones marked as new', async () => {
    openApp('/notifications', [ready, confirmed, alreadyRead])

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Notifications' }),
    ).toBeInTheDocument()
    await screen.findByText(ready.message)
    const readyItem = findNotificationItem(ready.message)
    expect(readyItem.getByText('New')).toBeInTheDocument()
    expect(readyItem.getByRole('button', { name: /Mark as read/ })).toBeInTheDocument()

    const readItem = findNotificationItem(alreadyRead.message)
    expect(readItem.queryByText('New')).not.toBeInTheDocument()
    expect(readItem.queryByRole('button', { name: /Mark as read/ })).not.toBeInTheDocument()
  })

  it('marks one notification as read and lowers the header count', async () => {
    const api = openApp('/notifications', [confirmed, ready])
    const user = userEvent.setup()
    const navigation = await findAccountNavigation()
    await navigation.findByRole('link', { name: 'Notifications, 2 unread' })

    await user.click(
      await screen.findByRole('button', { name: `Mark as read: ${confirmed.message}` }),
    )

    expect(await navigation.findByRole('link', { name: 'Notifications, 1 unread' })).toBeInTheDocument()
    expect(findNotificationItem(confirmed.message).queryByText('New')).not.toBeInTheDocument()
    expect(findNotificationItem(ready.message).getByText('New')).toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/notifications/1/read')).toHaveLength(1)
  })

  it('marks everything as read at once', async () => {
    const api = openApp('/notifications', [confirmed, ready])
    const user = userEvent.setup()
    const navigation = await findAccountNavigation()

    await user.click(await screen.findByRole('button', { name: 'Mark all as read' }))

    expect(await navigation.findByRole('link', { name: 'Notifications' })).toBeInTheDocument()
    expect(screen.queryByText('New')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mark all as read' })).not.toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/notifications/read-all')).toHaveLength(1)
  })

  it('offers no mark-all button when nothing is unread', async () => {
    openApp('/notifications', [alreadyRead])

    await screen.findByText(alreadyRead.message)

    expect(screen.queryByRole('button', { name: 'Mark all as read' })).not.toBeInTheDocument()
  })

  it('explains what will appear when there are no notifications', async () => {
    openApp('/notifications')

    expect(await screen.findByText(/You have no notifications yet/)).toBeInTheDocument()
  })

  it('is available to farmers as well as customers', async () => {
    openApp('/notifications', [], farmer)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Notifications' }),
    ).toBeInTheDocument()
  })

  it('sends a visitor who is not signed in to the login page', async () => {
    installFakeApi()
    renderApp('/notifications')

    expect(await screen.findByRole('heading', { level: 1, name: 'Login' })).toBeInTheDocument()
  })

  it('shows an error with a retry when notifications cannot be loaded', async () => {
    const api = openApp('/notifications', [confirmed])
    api.failNextRequest('GET', '/api/notifications', 500, 'Internal Server Error')
    const user = userEvent.setup()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your notifications could not be loaded.',
    )
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText(confirmed.message)).toBeInTheDocument()
  })

  it('is reached from the header link', async () => {
    openApp('/customer', [confirmed])
    const user = userEvent.setup()
    const navigation = await findAccountNavigation()

    await user.click(await navigation.findByRole('link', { name: 'Notifications, 1 unread' }))

    expect(await screen.findByText(confirmed.message)).toBeInTheDocument()
  })
})
