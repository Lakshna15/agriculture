import { useRef, useState, type FormEvent } from 'react'
import { describeApiError } from '../../api/errors.ts'
import {
  searchEvents,
  type EventReservation,
  type EventSearchResult,
  type FarmEventType,
} from '../../api/events.ts'
import EventSearchResultCard from '../../components/event/EventSearchResultCard.tsx'
import FormError from '../../components/FormError.tsx'
import LocationFields from '../../components/search/LocationFields.tsx'
import SelectField from '../../components/SelectField.tsx'
import SubmitButton from '../../components/SubmitButton.tsx'
import { farmEventTypeOptions } from '../../data/eventOptions.ts'
import {
  DEFAULT_SEARCH_RADIUS_MILES,
  searchRadiusMilesOptions,
} from '../../data/productOptions.ts'
import {
  LATITUDE_LIMIT,
  LONGITUDE_LIMIT,
  latitudeErrorMessage,
  longitudeErrorMessage,
  parseCoordinate,
} from '../../lib/coordinates.ts'
import {
  readSearchLocation,
  storeSearchLocation,
  type SearchLocation,
} from '../../lib/searchLocation.ts'

const radiusOptions = searchRadiusMilesOptions.map((miles) => ({
  value: String(miles),
  label: `${miles} miles`,
}))

type SearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  | { status: 'loaded'; results: EventSearchResult[]; radiusMiles: number }

/** Search for upcoming farm experiences nearby and reserve places at them. */
export default function ExperiencesPage() {
  const [location, setLocation] = useState<SearchLocation>(readSearchLocation)
  const [radiusMiles, setRadiusMiles] = useState(String(DEFAULT_SEARCH_RADIUS_MILES))
  const [eventType, setEventType] = useState<FarmEventType | ''>('')
  const [formError, setFormError] = useState<string | null>(null)
  const [searchState, setSearchState] = useState<SearchState>({ status: 'idle' })
  // Identifies the newest search so that a slower, older response cannot replace its results.
  const latestSearchNumber = useRef(0)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const latitude = parseCoordinate(location.latitude, LATITUDE_LIMIT)
    if (latitude === null) {
      setFormError(latitudeErrorMessage)
      return
    }
    const longitude = parseCoordinate(location.longitude, LONGITUDE_LIMIT)
    if (longitude === null) {
      setFormError(longitudeErrorMessage)
      return
    }

    setFormError(null)
    setSearchState({ status: 'loading' })
    storeSearchLocation(location)
    const searchNumber = ++latestSearchNumber.current
    const searchedRadiusMiles = Number(radiusMiles)

    try {
      const results = await searchEvents({
        latitude,
        longitude,
        radiusMiles: searchedRadiusMiles,
        eventType,
      })
      if (searchNumber === latestSearchNumber.current) {
        setSearchState({ status: 'loaded', results, radiusMiles: searchedRadiusMiles })
      }
    } catch (error) {
      if (searchNumber === latestSearchNumber.current) {
        setSearchState({ status: 'failed', message: describeApiError(error) })
      }
    }
  }

  function showReducedSpots(reservation: EventReservation) {
    setSearchState((current) => {
      if (current.status !== 'loaded') {
        return current
      }
      const results = current.results.map((result) =>
        result.event.id === reservation.event.id
          ? {
              ...result,
              event: {
                ...result.event,
                spots_remaining: result.event.spots_remaining - reservation.party_size,
              },
            }
          : result,
      )
      return { ...current, results }
    })
  }

  return (
    <>
      <section
        aria-labelledby="experience-search-heading"
        className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <h2
          id="experience-search-heading"
          className="text-xl font-semibold tracking-tight text-stone-900"
        >
          Find farm experiences
        </h2>
        <p className="mt-1 text-sm text-stone-600">
          Pick-your-own days, farm tours and other events hosted by farms near you.
        </p>
        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          <FormError message={formError} />
          <LocationFields location={location} onChange={setLocation} />
          <div className="grid gap-5 sm:grid-cols-2">
            <SelectField
              label="Radius"
              name="radius_miles"
              options={radiusOptions}
              value={radiusMiles}
              onChange={(event) => setRadiusMiles(event.target.value)}
            />
            <SelectField
              label="Type of experience"
              name="event_type"
              placeholder="All experiences"
              options={farmEventTypeOptions}
              value={eventType}
              onChange={(event) => setEventType(event.target.value as FarmEventType | '')}
            />
          </div>
          <div className="sm:w-44">
            <SubmitButton
              label="Search"
              submittingLabel="Searching…"
              isSubmitting={searchState.status === 'loading'}
            />
          </div>
        </form>
      </section>

      <section aria-labelledby="experience-results-heading" aria-live="polite" className="mt-8">
        <h2 id="experience-results-heading" className="sr-only">
          Farm experiences found
        </h2>

        {searchState.status === 'idle' && (
          <p className="text-center text-stone-600">
            Enter your location to see upcoming experiences at nearby farms.
          </p>
        )}

        {searchState.status === 'loading' && (
          <p role="status" className="text-center text-stone-600">
            Searching nearby farms…
          </p>
        )}

        {searchState.status === 'failed' && (
          <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            The search could not be completed. {searchState.message}
          </p>
        )}

        {searchState.status === 'loaded' && searchState.results.length === 0 && (
          <div className="rounded-xl border border-dashed border-stone-300 bg-white p-8 text-center">
            <p className="font-semibold text-stone-900">
              No upcoming farm experiences within {searchState.radiusMiles} miles.
            </p>
            <p className="mx-auto mt-2 max-w-md text-sm text-stone-600">
              Try a wider radius or a different type of experience.
            </p>
          </div>
        )}

        {searchState.status === 'loaded' && searchState.results.length > 0 && (
          <ul className="space-y-3">
            {searchState.results.map((result) => (
              <EventSearchResultCard
                key={result.event.id}
                result={result}
                onReserved={showReducedSpots}
              />
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
