import { useId } from 'react'
import type { ReservationStatus } from '../../api/reservations.ts'
import { reservationActionsFor } from '../../lib/reservations.ts'
import { useAsyncData } from '../../lib/useAsyncData.ts'
import { primaryButtonClassName } from '../buttonStyles.ts'
import ReservationCard from './ReservationCard.tsx'

type ReservationSectionProps<Reservation extends { id: number; status: ReservationStatus }> = {
  heading: string
  emptyMessage: string
  /** Whose view this is, which decides the status changes on offer. */
  side: 'customer' | 'farmer'
  /** Must keep the same identity between renders; see useAsyncData. */
  load: () => Promise<Reservation[]>
  describe: (reservation: Reservation) => { title: string; facts: string[] }
  changeStatus: (reservation: Reservation, newStatus: ReservationStatus) => Promise<Reservation>
}

/** A list of product or event reservations with loading, empty and error states. */
export default function ReservationSection<
  Reservation extends { id: number; status: ReservationStatus },
>({ heading, emptyMessage, side, load, describe, changeStatus }: ReservationSectionProps<Reservation>) {
  const headingId = useId()
  const { state, reload, updateData } = useAsyncData(load)

  async function handleChangeStatus(reservation: Reservation, newStatus: ReservationStatus) {
    const updatedReservation = await changeStatus(reservation, newStatus)
    updateData((reservations) =>
      reservations.map((current) =>
        current.id === updatedReservation.id ? updatedReservation : current,
      ),
    )
  }

  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId} className="text-xl font-semibold tracking-tight text-stone-900">
        {heading}
      </h2>
      <div className="mt-4">
        {state.status === 'loading' && (
          <p role="status" className="text-stone-600">
            Loading…
          </p>
        )}

        {state.status === 'failed' && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4">
            <p role="alert" className="text-sm text-red-800">
              These reservations could not be loaded. {state.message}
            </p>
            <button type="button" onClick={reload} className={`mt-3 ${primaryButtonClassName}`}>
              Try again
            </button>
          </div>
        )}

        {state.status === 'loaded' && state.data.length === 0 && (
          <p className="rounded-xl border border-dashed border-stone-300 bg-white p-6 text-center text-sm text-stone-600">
            {emptyMessage}
          </p>
        )}

        {state.status === 'loaded' && state.data.length > 0 && (
          <ul className="space-y-3">
            {state.data.map((reservation) => (
              <ReservationCard
                key={reservation.id}
                {...describe(reservation)}
                status={reservation.status}
                actions={reservationActionsFor(side, reservation.status)}
                onChangeStatus={(newStatus) => handleChangeStatus(reservation, newStatus)}
              />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
