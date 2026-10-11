import { apiRequest } from './client.ts'
import type { ReservationFarm, ReservationStatus } from './reservations.ts'

export type FarmEventType =
  | 'STRAWBERRY_PICKING'
  | 'APPLE_PICKING'
  | 'PUMPKIN_PICKING'
  | 'VEGETABLE_PICKING'
  | 'FARM_TOUR'
  | 'OTHER'

export type FarmEvent = {
  id: number
  farm_id: number
  title: string
  description: string | null
  event_type: FarmEventType
  /** An ISO calendar date, for example "2026-06-01". */
  event_date: string
  /** 24-hour times, for example "09:00:00". */
  start_time: string
  end_time: string
  /** Per person, as text such as "12.00". "0.00" means free. */
  price: string
  capacity: number
  spots_remaining: number
  created_at: string
}

export type NewFarmEvent = Omit<FarmEvent, 'id' | 'farm_id' | 'spots_remaining' | 'created_at'>

export type EventSearchCriteria = {
  latitude: number
  longitude: number
  radiusMiles: number
  /** An empty string means every type. */
  eventType: FarmEventType | ''
}

export type EventSearchResult = {
  event: FarmEvent
  farm: { id: number; farm_name: string; city: string; state: string }
  distance_miles: number
}

export type EventReservation = {
  id: number
  party_size: number
  status: ReservationStatus
  created_at: string
  customer_name: string
  event: Pick<
    FarmEvent,
    'id' | 'title' | 'event_type' | 'event_date' | 'start_time' | 'end_time' | 'price'
  >
  farm: ReservationFarm
}

export function createFarmEvent(accessToken: string, event: NewFarmEvent): Promise<FarmEvent> {
  return apiRequest<FarmEvent>('/api/events', { method: 'POST', body: event, accessToken })
}

export function fetchMyFarmEvents(accessToken: string): Promise<FarmEvent[]> {
  return apiRequest<FarmEvent[]>('/api/events/mine', { accessToken })
}

export function searchEvents(criteria: EventSearchCriteria): Promise<EventSearchResult[]> {
  const params = new URLSearchParams({
    latitude: String(criteria.latitude),
    longitude: String(criteria.longitude),
    radius_miles: String(criteria.radiusMiles),
  })
  if (criteria.eventType !== '') {
    params.set('event_type', criteria.eventType)
  }
  return apiRequest<EventSearchResult[]>(`/api/events/search?${params}`)
}

export function reserveEvent(
  accessToken: string,
  eventId: number,
  partySize: number,
): Promise<EventReservation> {
  return apiRequest<EventReservation>('/api/event-reservations', {
    method: 'POST',
    body: { event_id: eventId, party_size: partySize },
    accessToken,
  })
}

export function fetchMyEventReservations(accessToken: string): Promise<EventReservation[]> {
  return apiRequest<EventReservation[]>('/api/event-reservations/mine', { accessToken })
}

export function fetchFarmEventReservations(accessToken: string): Promise<EventReservation[]> {
  return apiRequest<EventReservation[]>('/api/event-reservations/farm', { accessToken })
}

export function updateEventReservationStatus(
  accessToken: string,
  reservationId: number,
  status: ReservationStatus,
): Promise<EventReservation> {
  return apiRequest<EventReservation>(`/api/event-reservations/${reservationId}/status`, {
    method: 'PATCH',
    body: { status },
    accessToken,
  })
}
