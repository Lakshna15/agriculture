import { useCallback } from 'react'
import {
  fetchFarmEventReservations,
  updateEventReservationStatus,
  type EventReservation,
} from '../../api/events.ts'
import {
  fetchFarmProductReservations,
  updateProductReservationStatus,
  type ProductReservation,
} from '../../api/reservations.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import ReservationSection from '../../components/reservation/ReservationSection.tsx'
import { productUnitLabels } from '../../data/productOptions.ts'
import { formatDate, formatTime } from '../../lib/format.ts'

function describeProductReservation(reservation: ProductReservation) {
  const unitLabel = productUnitLabels[reservation.product.unit]
  return {
    title: reservation.product.name,
    facts: [
      `Reserved by ${reservation.customer_name}`,
      `${reservation.quantity} ${unitLabel} · Pickup ${formatDate(reservation.pickup_date)} at ${formatTime(reservation.pickup_time)}`,
    ],
  }
}

function describeEventReservation(reservation: EventReservation) {
  const { event } = reservation
  return {
    title: event.title,
    facts: [
      `Reserved by ${reservation.customer_name} · party of ${reservation.party_size}`,
      `${formatDate(event.event_date)}, ${formatTime(event.start_time)} to ${formatTime(event.end_time)}`,
    ],
  }
}

/** Reservations customers have made with the signed-in farmer's farm. */
export default function FarmReservationsPage() {
  const accessToken = useAccessToken()
  const loadProductReservations = useCallback(
    () => fetchFarmProductReservations(accessToken),
    [accessToken],
  )
  const loadEventReservations = useCallback(
    () => fetchFarmEventReservations(accessToken),
    [accessToken],
  )

  return (
    <div className="space-y-10">
      <ReservationSection
        heading="Product reservations"
        emptyMessage="No one has reserved your products yet. Reservations appear here as customers make them."
        side="farmer"
        load={loadProductReservations}
        describe={describeProductReservation}
        changeStatus={(reservation, newStatus) =>
          updateProductReservationStatus(accessToken, reservation.id, newStatus)
        }
      />
      <ReservationSection
        heading="Event reservations"
        emptyMessage="No one has reserved a place at your events yet."
        side="farmer"
        load={loadEventReservations}
        describe={describeEventReservation}
        changeStatus={(reservation, newStatus) =>
          updateEventReservationStatus(accessToken, reservation.id, newStatus)
        }
      />
    </div>
  )
}
