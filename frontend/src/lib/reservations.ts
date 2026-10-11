import type { ReservationFarm, ReservationStatus } from '../api/reservations.ts'

export const reservationStatusLabels: Record<ReservationStatus, string> = {
  PENDING: 'Pending',
  CONFIRMED: 'Confirmed',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
}

export type ReservationAction = { label: string; newStatus: ReservationStatus }

const CONFIRM: ReservationAction = { label: 'Confirm', newStatus: 'CONFIRMED' }
const COMPLETE: ReservationAction = { label: 'Mark completed', newStatus: 'COMPLETED' }
const CANCEL: ReservationAction = { label: 'Cancel', newStatus: 'CANCELLED' }

/**
 * The status changes each side may make, mirroring the rules the API enforces:
 * the farm confirms and completes, either side may cancel, and completed or
 * cancelled reservations are final.
 */
export function reservationActionsFor(
  side: 'customer' | 'farmer',
  status: ReservationStatus,
): ReservationAction[] {
  if (status === 'PENDING') {
    return side === 'farmer' ? [CONFIRM, CANCEL] : [CANCEL]
  }
  if (status === 'CONFIRMED') {
    return side === 'farmer' ? [COMPLETE, CANCEL] : [CANCEL]
  }
  return []
}

export function formatFarmAddress(farm: ReservationFarm): string {
  return `${farm.address}, ${farm.city}, ${farm.state} ${farm.zip_code}`
}
