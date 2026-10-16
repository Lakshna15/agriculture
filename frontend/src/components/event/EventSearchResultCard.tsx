import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { describeApiError } from '../../api/errors.ts'
import { reserveEvent, type EventReservation, type EventSearchResult } from '../../api/events.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import { farmEventTypeLabels } from '../../data/eventOptions.ts'
import { formatDate, formatDistance, formatPriceOrFree, formatTime } from '../../lib/format.ts'
import { WHOLE_NUMBER_PATTERN } from '../../lib/numberInput.ts'
import { primaryButtonClassName, secondaryButtonClassName } from '../buttonStyles.ts'
import FormError from '../FormError.tsx'
import SubmitButton from '../SubmitButton.tsx'
import TextField from '../TextField.tsx'

type EventSearchResultCardProps = {
  result: EventSearchResult
  /** Called after a reservation is made, so the list can show the places that are left. */
  onReserved: (reservation: EventReservation) => void
}

export default function EventSearchResultCard({ result, onReserved }: EventSearchResultCardProps) {
  const { event, farm } = result
  const accessToken = useAccessToken()
  const [isReserving, setIsReserving] = useState(false)
  const [partySizeText, setPartySizeText] = useState('2')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [latestReservation, setLatestReservation] = useState<EventReservation | null>(null)

  const hasSpots = event.spots_remaining > 0

  async function handleSubmit(submitEvent: FormEvent<HTMLFormElement>) {
    submitEvent.preventDefault()

    const partySize = Number(partySizeText)
    const isValidPartySize =
      WHOLE_NUMBER_PATTERN.test(partySizeText.trim()) &&
      partySize >= 1 &&
      partySize <= event.spots_remaining
    if (!isValidPartySize) {
      setErrorMessage(`Party size must be a whole number between 1 and ${event.spots_remaining}.`)
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      const reservation = await reserveEvent(accessToken, event.id, partySize)
      setLatestReservation(reservation)
      setIsReserving(false)
      onReserved(reservation)
    } catch (error) {
      setErrorMessage(describeApiError(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <li className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-stone-900">{event.title}</h3>
          <p className="mt-0.5 text-sm text-stone-600">{farmEventTypeLabels[event.event_type]}</p>
        </div>
        <p className="shrink-0 text-right">
          <span className="text-lg font-semibold text-stone-900">
            {formatPriceOrFree(event.price)}
          </span>
          {Number(event.price) > 0 && <span className="text-sm text-stone-600"> / person</span>}
        </p>
      </div>

      {event.description && <p className="mt-3 text-sm text-stone-700">{event.description}</p>}

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-stone-200 pt-4 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs font-medium tracking-wide text-stone-500 uppercase">When</dt>
          <dd className="mt-0.5 text-stone-900">{formatDate(event.event_date)}</dd>
          <dd className="text-stone-600">
            {formatTime(event.start_time)} to {formatTime(event.end_time)}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium tracking-wide text-stone-500 uppercase">Farm</dt>
          <dd className="mt-0.5 text-stone-900">{farm.farm_name}</dd>
          <dd className="text-stone-600">
            {farm.city}, {farm.state}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium tracking-wide text-stone-500 uppercase">Distance</dt>
          <dd className="mt-0.5 text-stone-900">{formatDistance(result.distance_miles)}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium tracking-wide text-stone-500 uppercase">Places</dt>
          <dd className={`mt-0.5 ${hasSpots ? 'text-stone-900' : 'text-red-800'}`}>
            {hasSpots ? `${event.spots_remaining} of ${event.capacity} left` : 'Fully booked'}
          </dd>
        </div>
      </dl>

      {latestReservation && (
        <p
          role="status"
          className="mt-4 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900"
        >
          Reserved for a party of {latestReservation.party_size}.{' '}
          <Link to="/customer/reservations" className="font-medium underline underline-offset-4">
            View my reservations
          </Link>
        </p>
      )}

      {isReserving ? (
        <form onSubmit={handleSubmit} className="mt-4 space-y-4 border-t border-stone-200 pt-4">
          <FormError message={errorMessage} />
          <div className="sm:w-48">
            <TextField
              label="Party size"
              name="party_size"
              inputMode="numeric"
              required
              hint={`Up to ${event.spots_remaining}.`}
              value={partySizeText}
              onChange={(changeEvent) => setPartySizeText(changeEvent.target.value)}
            />
          </div>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={() => setIsReserving(false)}
              disabled={isSubmitting}
              className={secondaryButtonClassName}
            >
              Cancel
            </button>
            <div className="sm:w-48">
              <SubmitButton
                label="Confirm reservation"
                submittingLabel="Reserving…"
                isSubmitting={isSubmitting}
              />
            </div>
          </div>
        </form>
      ) : (
        hasSpots && (
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              // The label names the event so the buttons are distinguishable to a screen reader.
              aria-label={`Reserve ${event.title}`}
              onClick={() => setIsReserving(true)}
              className={primaryButtonClassName}
            >
              Reserve
            </button>
          </div>
        )
      )}
    </li>
  )
}
