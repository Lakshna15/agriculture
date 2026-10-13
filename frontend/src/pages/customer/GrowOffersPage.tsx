import { useCallback, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { describeApiError } from '../../api/errors.ts'
import {
  fetchMyCommitments,
  searchGrowOffers,
  type CropCommitment,
  type GrowOfferSearchResult,
} from '../../api/growOffers.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import { primaryButtonClassName, secondaryButtonClassName } from '../../components/buttonStyles.ts'
import FormError from '../../components/FormError.tsx'
import CommitmentProgress from '../../components/grow/CommitmentProgress.tsx'
import GrowOfferCard from '../../components/grow/GrowOfferCard.tsx'
import LocationFields from '../../components/search/LocationFields.tsx'
import SelectField from '../../components/SelectField.tsx'
import SubmitButton from '../../components/SubmitButton.tsx'
import TextField from '../../components/TextField.tsx'
import { growOfferStatusBadgeClassNames, growOfferStatusLabels } from '../../data/growOptions.ts'
import {
  DEFAULT_SEARCH_RADIUS_MILES,
  productUnitLabels,
  searchRadiusMilesOptions,
} from '../../data/productOptions.ts'
import {
  LATITUDE_LIMIT,
  LONGITUDE_LIMIT,
  latitudeErrorMessage,
  longitudeErrorMessage,
  parseCoordinate,
} from '../../lib/coordinates.ts'
import { formatDate, formatPrice } from '../../lib/format.ts'
import {
  readSearchLocation,
  storeSearchLocation,
  type SearchLocation,
} from '../../lib/searchLocation.ts'
import { useAsyncData } from '../../lib/useAsyncData.ts'

const radiusOptions = searchRadiusMilesOptions.map((miles) => ({
  value: String(miles),
  label: `${miles} miles`,
}))

type SearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  | { status: 'loaded'; results: GrowOfferSearchResult[]; radiusMiles: number }

/** Browse what nearby farmers are offering to grow, join an offer, and follow commitments. */
export default function GrowOffersPage() {
  const accessToken = useAccessToken()
  const loadCommitments = useCallback(() => fetchMyCommitments(accessToken), [accessToken])
  const {
    state: commitmentsState,
    reload: reloadCommitments,
    updateData: updateCommitments,
  } = useAsyncData(loadCommitments)

  const [location, setLocation] = useState<SearchLocation>(readSearchLocation)
  const [radiusMiles, setRadiusMiles] = useState(String(DEFAULT_SEARCH_RADIUS_MILES))
  const [crop, setCrop] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [searchState, setSearchState] = useState<SearchState>({ status: 'idle' })
  // Identifies the newest search so that a slower, older response cannot replace its results.
  const latestSearchNumber = useRef(0)

  const commitments = commitmentsState.status === 'loaded' ? commitmentsState.data : []

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
      const results = await searchGrowOffers({
        latitude,
        longitude,
        radiusMiles: searchedRadiusMiles,
        crop,
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

  function showJoinedOffer(commitment: CropCommitment) {
    updateCommitments((current) => [commitment, ...current])
    // The response carries the offer's new progress and status, which may now be CONFIRMED.
    setSearchState((current) => {
      if (current.status !== 'loaded') {
        return current
      }
      const results = current.results.map((result) =>
        result.offer.id === commitment.offer.id ? { ...result, offer: commitment.offer } : result,
      )
      return { ...current, results }
    })
  }

  return (
    <div className="space-y-10">
      <div>
        <section
          aria-labelledby="grow-offer-search-heading"
          className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8"
        >
          <h2
            id="grow-offer-search-heading"
            className="text-xl font-semibold tracking-tight text-stone-900"
          >
            Browse grow offers
          </h2>
          <p className="mt-1 text-sm text-stone-600">
            Farmers offer to grow a crop if enough customers commit to it. Join an offer to help
            it reach its target.
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
              <TextField
                label="Crop"
                name="crop"
                type="search"
                maxLength={80}
                hint="Optional. Leave empty to see every offer nearby."
                value={crop}
                onChange={(event) => setCrop(event.target.value)}
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

        <section aria-labelledby="grow-offer-results-heading" aria-live="polite" className="mt-8">
          <h2 id="grow-offer-results-heading" className="sr-only">
            Grow offers found
          </h2>

          {searchState.status === 'idle' && (
            <p className="text-center text-stone-600">
              Enter your location to see what nearby farmers are offering to grow.
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
                No grow offers within {searchState.radiusMiles} miles yet.
              </p>
              <p className="mx-auto mt-2 max-w-md text-sm text-stone-600">
                Farmers create offers in response to crop requests. Request the crop you want
                under Crop requests so nearby farmers can see the demand.
              </p>
            </div>
          )}

          {searchState.status === 'loaded' && searchState.results.length > 0 && (
            <ul className="space-y-3">
              {searchState.results.map((result) => (
                <GrowOfferCard
                  key={result.offer.id}
                  result={result}
                  myCommitment={commitments.find(
                    (commitment) => commitment.offer.id === result.offer.id,
                  )}
                  onJoined={showJoinedOffer}
                />
              ))}
            </ul>
          )}
        </section>
      </div>

      <section aria-labelledby="my-commitments-heading">
        <h2
          id="my-commitments-heading"
          className="text-xl font-semibold tracking-tight text-stone-900"
        >
          My commitments
        </h2>
        <div className="mt-4">
          {commitmentsState.status === 'loading' && (
            <p role="status" className="text-stone-600">
              Loading your commitments…
            </p>
          )}

          {commitmentsState.status === 'failed' && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4">
              <p role="alert" className="text-sm text-red-800">
                Your commitments could not be loaded. {commitmentsState.message}
              </p>
              <button
                type="button"
                onClick={reloadCommitments}
                className={`mt-3 ${primaryButtonClassName}`}
              >
                Try again
              </button>
            </div>
          )}

          {commitmentsState.status === 'loaded' && commitments.length === 0 && (
            <p className="rounded-xl border border-dashed border-stone-300 bg-white p-6 text-center text-sm text-stone-600">
              You have not joined any grow offers yet.
            </p>
          )}

          {commitmentsState.status === 'loaded' && commitments.length > 0 && (
            <ul className="space-y-3">
              {commitments.map((commitment) => {
                const { offer, farm } = commitment
                const unitLabel = productUnitLabels[offer.unit]
                return (
                  <li key={commitment.id} className="rounded-lg border border-stone-200 bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="font-semibold text-stone-900">{offer.crop_name}</h3>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${growOfferStatusBadgeClassNames[offer.status]}`}
                      >
                        {growOfferStatusLabels[offer.status]}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-stone-600">
                      You committed to {commitment.quantity} {unitLabel} at about{' '}
                      {formatPrice(offer.estimated_price)} / {unitLabel}
                    </p>
                    <p className="text-sm text-stone-600">
                      {farm.farm_name}, {farm.city}, {farm.state} · Expected harvest{' '}
                      {formatDate(offer.expected_harvest_date)}
                    </p>
                    <div className="mt-3 sm:w-80">
                      <CommitmentProgress offer={offer} />
                    </div>
                    <Link
                      to={`/customer/grow-offers/${offer.id}`}
                      aria-label={`View crop journey for ${offer.crop_name}`}
                      className={`mt-4 inline-block ${secondaryButtonClassName}`}
                    >
                      View crop journey
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}
