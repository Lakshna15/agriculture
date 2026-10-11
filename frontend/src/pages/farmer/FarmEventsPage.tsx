import { useCallback, useState } from 'react'
import {
  createFarmEvent,
  fetchMyFarmEvents,
  type FarmEvent,
  type NewFarmEvent,
} from '../../api/events.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import { primaryButtonClassName } from '../../components/buttonStyles.ts'
import FarmEventForm from '../../components/event/FarmEventForm.tsx'
import { farmEventTypeLabels } from '../../data/eventOptions.ts'
import { formatDate, formatPriceOrFree, formatTime } from '../../lib/format.ts'
import { useAsyncData } from '../../lib/useAsyncData.ts'

function byDateAndTime(first: FarmEvent, second: FarmEvent): number {
  // ISO dates and 24-hour times sort correctly as text.
  return (
    first.event_date.localeCompare(second.event_date) ||
    first.start_time.localeCompare(second.start_time)
  )
}

function describePrice(event: FarmEvent): string {
  const price = formatPriceOrFree(event.price)
  return Number(event.price) > 0 ? `${price} per person` : price
}

/** The farm experiences the signed-in farmer hosts, and a form to add one. */
export default function FarmEventsPage() {
  const accessToken = useAccessToken()
  const loadEvents = useCallback(() => fetchMyFarmEvents(accessToken), [accessToken])
  const { state, reload, updateData } = useAsyncData(loadEvents)
  const [isCreating, setIsCreating] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  async function handleCreate(newEvent: NewFarmEvent) {
    const event = await createFarmEvent(accessToken, newEvent)
    updateData((events) => [...events, event].sort(byDateAndTime))
    setIsCreating(false)
    setNotice(`${event.title} has been created.`)
  }

  function startCreating() {
    setNotice(null)
    setIsCreating(true)
  }

  return (
    <section aria-labelledby="farm-events-heading">
      <div className="flex items-center justify-between gap-4">
        <h2
          id="farm-events-heading"
          className="text-xl font-semibold tracking-tight text-stone-900"
        >
          Farm events
        </h2>
        {state.status === 'loaded' && !isCreating && (
          <button type="button" onClick={startCreating} className={primaryButtonClassName}>
            Create Farm Event
          </button>
        )}
      </div>

      <div className="mt-4 space-y-4">
        {notice && (
          <p
            role="status"
            className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900"
          >
            {notice}
          </p>
        )}

        {state.status === 'loading' && (
          <p role="status" className="text-stone-600">
            Loading your events…
          </p>
        )}

        {state.status === 'failed' && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4">
            <p role="alert" className="text-sm text-red-800">
              Your events could not be loaded. {state.message}
            </p>
            <button type="button" onClick={reload} className={`mt-3 ${primaryButtonClassName}`}>
              Try again
            </button>
          </div>
        )}

        {isCreating && (
          <FarmEventForm onSubmit={handleCreate} onCancel={() => setIsCreating(false)} />
        )}

        {state.status === 'loaded' && state.data.length === 0 && !isCreating && (
          <div className="rounded-xl border border-dashed border-stone-300 bg-white p-8 text-center">
            <p className="font-semibold text-stone-900">You have not created any farm events yet</p>
            <p className="mx-auto mt-2 max-w-md text-sm text-stone-600">
              Host a pick-your-own day or a farm tour and let nearby customers reserve a place.
            </p>
          </div>
        )}

        {state.status === 'loaded' && state.data.length > 0 && (
          <ul className="space-y-3">
            {state.data.map((event) => (
              <li key={event.id} className="rounded-lg border border-stone-200 bg-white p-4">
                <h3 className="font-semibold text-stone-900">{event.title}</h3>
                <p className="mt-1 text-sm text-stone-600">
                  {farmEventTypeLabels[event.event_type]} · {formatDate(event.event_date)},{' '}
                  {formatTime(event.start_time)} to {formatTime(event.end_time)} ·{' '}
                  {describePrice(event)}
                </p>
                <p className="mt-1 text-sm text-stone-900">
                  {event.spots_remaining} of {event.capacity} places remaining
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
