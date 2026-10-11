import { useState } from 'react'
import { describeApiError } from '../../api/errors.ts'
import type { ReservationStatus } from '../../api/reservations.ts'
import { reservationStatusLabels, type ReservationAction } from '../../lib/reservations.ts'
import { secondaryButtonClassName } from '../buttonStyles.ts'

const statusBadgeClassNames: Record<ReservationStatus, string> = {
  PENDING: 'bg-amber-100 text-amber-900',
  CONFIRMED: 'bg-green-100 text-green-900',
  COMPLETED: 'bg-stone-200 text-stone-700',
  CANCELLED: 'bg-red-100 text-red-900',
}

type ReservationCardProps = {
  /** What was reserved: a product name or an event title. */
  title: string
  status: ReservationStatus
  /** Lines of detail shown under the title. */
  facts: string[]
  /** The status changes the viewer may make right now. */
  actions: ReservationAction[]
  onChangeStatus: (newStatus: ReservationStatus) => Promise<void>
}

export default function ReservationCard({
  title,
  status,
  facts,
  actions,
  onChangeStatus,
}: ReservationCardProps) {
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isBusy, setIsBusy] = useState(false)

  async function changeStatus(newStatus: ReservationStatus) {
    setErrorMessage(null)
    setIsBusy(true)
    try {
      await onChangeStatus(newStatus)
    } catch (error) {
      setErrorMessage(describeApiError(error))
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <li className="rounded-lg border border-stone-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-stone-900">{title}</h3>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadgeClassNames[status]}`}
        >
          {reservationStatusLabels[status]}
        </span>
      </div>
      <ul className="mt-1 space-y-0.5 text-sm text-stone-600">
        {facts.map((fact) => (
          <li key={fact}>{fact}</li>
        ))}
      </ul>

      {errorMessage && (
        <p role="alert" className="mt-3 text-sm text-red-800">
          {errorMessage}
        </p>
      )}

      {actions.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {actions.map((action) => (
            <button
              key={action.newStatus}
              type="button"
              // The label names the reservation so the buttons are distinguishable to a screen reader.
              aria-label={`${action.label} reservation for ${title}`}
              onClick={() => void changeStatus(action.newStatus)}
              disabled={isBusy}
              className={secondaryButtonClassName}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </li>
  )
}
