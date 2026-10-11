import { useCallback } from 'react'
import {
  fetchMyEventReservations,
  updateEventReservationStatus,
  type EventReservation,
} from '../../api/events.ts'
import {
  fetchMyProductReservations,
  updateProductReservationStatus,
  type ProductReservation,
} from '../../api/reservations.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import ReservationSection from '../../components/reservation/ReservationSection.tsx'
import { productUnitLabels } from '../../data/productOptions.ts'
import { formatDate, formatPriceOrFree, formatTime } from '../../lib/format.ts'
import { formatFarmAddress } from '../../lib/reservations.ts'

function describeProductReservation(reservation: ProductReservation) {
  const unitLabel = productUnitLabels[reservation.product.unit]
  return {
    title: reservation.product.name,
    facts: [
      `${reservation.quantity} ${unitLabel} · Pickup ${formatDate(reservation.pickup_date)} at ${formatTime(reservation.pickup_time)}`,
      `${reservation.farm.farm_name}, ${formatFarmAddress(reservation.farm)}`,
      ...(reservation.farm.phone ? [`Farm phone: ${reservation.farm.phone}`] : []),
    ],
  }
}

function describeEventReservation(reservation: EventReservation) {
  const { event, farm } = reservation
  return {
    title: event.title,
    facts: [
      `Party of ${reservation.party_size} · ${formatDate(event.event_date)}, ${formatTime(event.start_time)} to ${formatTime(event.end_time)}`,
      `${formatPriceOrFree(event.price)}${Number(event.price) > 0 ? ' per person' : ''}`,
      `${farm.farm_name}, ${formatFarmAddress(farm)}`,
      ...(farm.phone ? [`Farm phone: ${farm.phone}`] : []),
    ],
  }
}

/** Everything the signed-in customer has reserved, with the option to cancel. */
export default function CustomerReservationsPage() {
  const accessToken = useAccessToken()
  const loadProductReservations = useCallback(
    () => fetchMyProductReservations(accessToken),
    [accessToken],
  )
  const loadEventReservations = useCallback(
    () => fetchMyEventReservations(accessToken),
    [accessToken],
  )

  return (
    <div className="space-y-10">
      <ReservationSection
        heading="Product reservations"
        emptyMessage="You have not reserved any products yet. Search nearby products to reserve something for pickup."
        side="customer"
        load={loadProductReservations}
        describe={describeProductReservation}
        changeStatus={(reservation, newStatus) =>
          updateProductReservationStatus(accessToken, reservation.id, newStatus)
        }
      />
      <ReservationSection
        heading="Farm experience reservations"
        emptyMessage="You have not reserved any farm experiences yet. Look under Farm experiences to find one nearby."
        side="customer"
        load={loadEventReservations}
        describe={describeEventReservation}
        changeStatus={(reservation, newStatus) =>
          updateEventReservationStatus(accessToken, reservation.id, newStatus)
        }
      />
    </div>
  )
}
