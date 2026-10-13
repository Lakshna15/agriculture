import { useCallback, useState } from 'react'
import { useOutletContext } from 'react-router'
import { describeApiError } from '../api/errors.ts'
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type Notification,
} from '../api/notifications.ts'
import { useAccessToken } from '../auth/useAuth.ts'
import type { AppLayoutContext } from '../components/AppLayout.tsx'
import { primaryButtonClassName, secondaryButtonClassName } from '../components/buttonStyles.ts'
import { formatDateTime } from '../lib/format.ts'
import { useAsyncData } from '../lib/useAsyncData.ts'

/** The signed-in user's in-app notifications, newest first. */
export default function NotificationsPage() {
  const accessToken = useAccessToken()
  const { refreshUnreadNotificationCount } = useOutletContext<AppLayoutContext>()
  const loadNotifications = useCallback(() => fetchNotifications(accessToken), [accessToken])
  const { state, reload, updateData } = useAsyncData(loadNotifications)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const hasUnread = state.status === 'loaded' && state.data.some((notification) => !notification.read)

  async function handleMarkRead(notification: Notification) {
    setErrorMessage(null)
    try {
      const readNotification = await markNotificationRead(accessToken, notification.id)
      updateData((notifications) =>
        notifications.map((current) =>
          current.id === readNotification.id ? readNotification : current,
        ),
      )
      refreshUnreadNotificationCount()
    } catch (error) {
      setErrorMessage(describeApiError(error))
    }
  }

  async function handleMarkAllRead() {
    setErrorMessage(null)
    try {
      await markAllNotificationsRead(accessToken)
      updateData((notifications) =>
        notifications.map((notification) => ({ ...notification, read: true })),
      )
      refreshUnreadNotificationCount()
    } catch (error) {
      setErrorMessage(describeApiError(error))
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-bold tracking-tight text-stone-900">Notifications</h1>
        {hasUnread && (
          <button
            type="button"
            onClick={() => void handleMarkAllRead()}
            className={secondaryButtonClassName}
          >
            Mark all as read
          </button>
        )}
      </div>
      <p className="mt-2 text-stone-600">
        News about the crops you committed to: confirmations, progress updates and harvests.
      </p>

      <div className="mt-8">
        {errorMessage && (
          <p role="alert" className="mb-3 text-sm text-red-800">
            {errorMessage}
          </p>
        )}

        {state.status === 'loading' && (
          <p role="status" className="text-stone-600">
            Loading your notifications…
          </p>
        )}

        {state.status === 'failed' && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4">
            <p role="alert" className="text-sm text-red-800">
              Your notifications could not be loaded. {state.message}
            </p>
            <button type="button" onClick={reload} className={`mt-3 ${primaryButtonClassName}`}>
              Try again
            </button>
          </div>
        )}

        {state.status === 'loaded' && state.data.length === 0 && (
          <p className="rounded-xl border border-dashed border-stone-300 bg-white p-6 text-center text-sm text-stone-600">
            You have no notifications yet. When a grow offer you joined is confirmed, updated
            or ready, you will hear about it here.
          </p>
        )}

        {state.status === 'loaded' && state.data.length > 0 && (
          <ul className="space-y-3">
            {state.data.map((notification) => (
              <li
                key={notification.id}
                className={`rounded-lg border p-4 ${
                  notification.read ? 'border-stone-200 bg-white' : 'border-green-300 bg-green-50'
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm text-stone-900">
                      {!notification.read && (
                        <span className="mr-2 rounded-full bg-green-700 px-2 py-0.5 text-xs font-medium text-white">
                          New
                        </span>
                      )}
                      {notification.message}
                    </p>
                    <time dateTime={notification.created_at} className="mt-1 block text-xs text-stone-500">
                      {formatDateTime(notification.created_at)}
                    </time>
                  </div>
                  {!notification.read && (
                    <button
                      type="button"
                      aria-label={`Mark as read: ${notification.message}`}
                      onClick={() => void handleMarkRead(notification)}
                      className={secondaryButtonClassName}
                    >
                      Mark as read
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}
