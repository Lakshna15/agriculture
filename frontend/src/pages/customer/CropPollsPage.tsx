import { useCallback, useRef, useState, type FormEvent } from 'react'
import {
  castCropVote,
  fetchMyCropVotes,
  searchCropPolls,
  type CropPollSearchResult,
  type CropVoteResult,
} from '../../api/cropPolls.ts'
import { describeApiError } from '../../api/errors.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import { primaryButtonClassName } from '../../components/buttonStyles.ts'
import FormError from '../../components/FormError.tsx'
import PollResults from '../../components/poll/PollResults.tsx'
import LocationFields from '../../components/search/LocationFields.tsx'
import SelectField from '../../components/SelectField.tsx'
import SubmitButton from '../../components/SubmitButton.tsx'
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
import { formatDistance } from '../../lib/format.ts'
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
  | { status: 'loaded'; results: CropPollSearchResult[]; radiusMiles: number }

type PollCardProps = {
  result: CropPollSearchResult
  /** The option the customer already voted for in this poll, if they have voted. */
  chosenOptionId: number | undefined
  onVoted: (vote: CropVoteResult) => void
}

function PollCard({ result, chosenOptionId, onVoted }: PollCardProps) {
  const { poll, farm } = result
  const accessToken = useAccessToken()
  const [selectedOptionId, setSelectedOptionId] = useState<number | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const hasVoted = chosenOptionId !== undefined

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (selectedOptionId === null) {
      setErrorMessage('Choose a crop to vote for.')
      return
    }
    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      onVoted(await castCropVote(accessToken, poll.id, selectedOptionId))
    } catch (error) {
      setErrorMessage(describeApiError(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <li className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
      <h3 className="font-semibold text-stone-900">{poll.question}</h3>
      <p className="mt-0.5 text-sm text-stone-600">
        {farm.farm_name} · {farm.city}, {farm.state} · {formatDistance(result.distance_miles)}
      </p>

      {hasVoted ? (
        <div className="mt-4">
          <PollResults poll={poll} chosenOptionId={chosenOptionId} />
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <FormError message={errorMessage} />
          <fieldset>
            <legend className="sr-only">{poll.question}</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {poll.options.map((option) => (
                <label
                  key={option.id}
                  className="flex cursor-pointer items-center gap-3 rounded-md border border-stone-300 p-3 has-checked:border-green-700 has-checked:bg-green-50"
                >
                  <input
                    type="radio"
                    name={`poll-${poll.id}`}
                    value={option.id}
                    checked={selectedOptionId === option.id}
                    onChange={() => setSelectedOptionId(option.id)}
                    className="accent-green-700"
                  />
                  <span className="text-sm font-medium text-stone-900">{option.crop_name}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="sm:w-40">
            <SubmitButton label="Vote" submittingLabel="Voting…" isSubmitting={isSubmitting} />
          </div>
        </form>
      )}
    </li>
  )
}

/** Find polls from nearby farms asking what to grow next, and vote in them. */
export default function CropPollsPage() {
  const accessToken = useAccessToken()
  const loadVotes = useCallback(() => fetchMyCropVotes(accessToken), [accessToken])
  const { state: votesState, reload: reloadVotes, updateData: updateVotes } = useAsyncData(loadVotes)

  const [location, setLocation] = useState<SearchLocation>(readSearchLocation)
  const [radiusMiles, setRadiusMiles] = useState(String(DEFAULT_SEARCH_RADIUS_MILES))
  const [formError, setFormError] = useState<string | null>(null)
  const [searchState, setSearchState] = useState<SearchState>({ status: 'idle' })
  // Identifies the newest search so that a slower, older response cannot replace its results.
  const latestSearchNumber = useRef(0)

  const votes = votesState.status === 'loaded' ? votesState.data : []

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
      const results = await searchCropPolls({
        latitude,
        longitude,
        radiusMiles: searchedRadiusMiles,
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

  function showVote(vote: CropVoteResult) {
    updateVotes((current) => [{ poll_id: vote.poll_id, option_id: vote.option_id }, ...current])
    setSearchState((current) => {
      if (current.status !== 'loaded') {
        return current
      }
      const results = current.results.map((result) =>
        result.poll.id === vote.poll.id ? { ...result, poll: vote.poll } : result,
      )
      return { ...current, results }
    })
  }

  return (
    <>
      <section
        aria-labelledby="poll-search-heading"
        className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <h2 id="poll-search-heading" className="text-xl font-semibold tracking-tight text-stone-900">
          Crop polls
        </h2>
        <p className="mt-1 text-sm text-stone-600">
          Nearby farmers ask what they should grow next. You get one vote in each poll.
        </p>
        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          <FormError message={formError} />
          <LocationFields location={location} onChange={setLocation} />
          <div className="sm:w-64">
            <SelectField
              label="Radius"
              name="radius_miles"
              options={radiusOptions}
              value={radiusMiles}
              onChange={(event) => setRadiusMiles(event.target.value)}
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

      <section aria-labelledby="poll-results-heading" aria-live="polite" className="mt-8">
        <h2 id="poll-results-heading" className="sr-only">
          Crop polls found
        </h2>

        {votesState.status === 'failed' && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4">
            <p role="alert" className="text-sm text-red-800">
              Your earlier votes could not be loaded. {votesState.message}
            </p>
            <button type="button" onClick={reloadVotes} className={`mt-3 ${primaryButtonClassName}`}>
              Try again
            </button>
          </div>
        )}

        {searchState.status === 'idle' && (
          <p className="text-center text-stone-600">
            Enter your location to see what nearby farmers are asking.
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
              No open crop polls within {searchState.radiusMiles} miles.
            </p>
            <p className="mx-auto mt-2 max-w-md text-sm text-stone-600">
              To tell farmers what you want without waiting for a poll, request a crop under
              Crop requests.
            </p>
          </div>
        )}

        {searchState.status === 'loaded' && searchState.results.length > 0 && (
          <ul className="space-y-3">
            {searchState.results.map((result) => (
              <PollCard
                key={result.poll.id}
                result={result}
                chosenOptionId={votes.find((vote) => vote.poll_id === result.poll.id)?.option_id}
                onVoted={showVote}
              />
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
