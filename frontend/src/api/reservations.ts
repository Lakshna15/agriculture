import { apiRequest } from './client.ts'
import type { ProductUnit } from './products.ts'

export type ReservationStatus = 'PENDING' | 'CONFIRMED' | 'COMPLETED' | 'CANCELLED'

/** Where a reserved product is collected, or a reserved experience takes place. */
export type ReservationFarm = {
  id: number
  farm_name: string
  address: string
  city: string
  state: string
  zip_code: string
  phone: string | null
}

export type ProductReservation = {
  id: number
  quantity: number
  /** An ISO calendar date, for example "2026-06-01". */
  pickup_date: string
  /** A 24-hour time, for example "10:30:00". */
  pickup_time: string
  status: ReservationStatus
  created_at: string
  updated_at: string
  customer_name: string
  product: { id: number; name: string; unit: ProductUnit }
  farm: ReservationFarm
}

export type NewProductReservation = {
  product_id: number
  quantity: number
  pickup_date: string
  pickup_time: string
}

export function reserveProduct(
  accessToken: string,
  reservation: NewProductReservation,
): Promise<ProductReservation> {
  return apiRequest<ProductReservation>('/api/reservations', {
    method: 'POST',
    body: reservation,
    accessToken,
  })
}

export function fetchMyProductReservations(accessToken: string): Promise<ProductReservation[]> {
  return apiRequest<ProductReservation[]>('/api/reservations/mine', { accessToken })
}

export function fetchFarmProductReservations(accessToken: string): Promise<ProductReservation[]> {
  return apiRequest<ProductReservation[]>('/api/reservations/farm', { accessToken })
}

export function updateProductReservationStatus(
  accessToken: string,
  reservationId: number,
  status: ReservationStatus,
): Promise<ProductReservation> {
  return apiRequest<ProductReservation>(`/api/reservations/${reservationId}/status`, {
    method: 'PATCH',
    body: { status },
    accessToken,
  })
}
