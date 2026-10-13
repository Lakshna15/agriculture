import { apiRequest } from './client.ts'

export type NotificationType =
  | 'GROW_OFFER_CONFIRMED'
  | 'CROP_UPDATE_POSTED'
  | 'CROP_READY'
  | 'GROW_OFFER_CANCELLED'

export type Notification = {
  id: number
  type: NotificationType
  message: string
  read: boolean
  created_at: string
}

export function fetchNotifications(accessToken: string): Promise<Notification[]> {
  return apiRequest<Notification[]>('/api/notifications', { accessToken })
}

export async function fetchUnreadNotificationCount(accessToken: string): Promise<number> {
  const { unread } = await apiRequest<{ unread: number }>('/api/notifications/unread-count', {
    accessToken,
  })
  return unread
}

export function markNotificationRead(
  accessToken: string,
  notificationId: number,
): Promise<Notification> {
  return apiRequest<Notification>(`/api/notifications/${notificationId}/read`, {
    method: 'POST',
    accessToken,
  })
}

export function markAllNotificationsRead(accessToken: string): Promise<void> {
  return apiRequest<void>('/api/notifications/read-all', { method: 'POST', accessToken })
}
