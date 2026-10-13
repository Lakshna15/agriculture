import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router'
import {
  completeGrowOffer,
  fetchCropUpdates,
  fetchGrowOfferDetail,
  postCropUpdate,
  type CropStage,
  type CropUpdate,
  type GrowOfferDetail,
  type NewCropUpdate,
} from '../api/cropJourney.ts'
import { describeApiError } from '../api/errors.ts'
import type { GrowOffer } from '../api/growOffers.ts'
import { useAccessToken } from '../auth/useAuth.ts'
import { primaryButtonClassName } from '../components/buttonStyles.ts'
import CommitmentProgress from '../components/grow/CommitmentProgress.tsx'
import CropJourney from '../components/grow/CropJourney.tsx'
import CropUpdateForm from '../components/grow/CropUpdateForm.tsx'
import { growOfferStatusBadgeClassNames, growOfferStatusLabels } from '../data/growOptions.ts'
import { cropStageOptions } from '../data/journeyOptions.ts'
import { productUnitLabels } from '../data/productOptions.ts'
import { formatDate, formatPrice } from '../lib/format.ts'
import { useAsyncData } from '../lib/useAsyncData.ts'

type JourneyData = { detail: GrowOfferDetail; updates: CropUpdate[] }

/**
 * The stages a farmer may post next, mirroring the API's rules: an offer that
 * is still open can only be planned, and a crop never goes back a stage.
 */
function selectableStages(offer: GrowOffer, updates: CropUpdate[]) {
  if (offer.status === 'OPEN') {
    return cropStageOptions.filter((option) => option.value === 'PLANNED')
  }
  const latestStage: CropStage | undefined = updates.at(-1)?.stage
  const firstAllowed = latestStage
    ? cropStageOptions.findIndex((option) => option.value === latestStage)
    : 0
  return cropStageOptions.slice(firstAllowed)
}

type CropJourneyPageProps = {
  /** Farmers get the controls for posting updates; customers only read. */
  audience: 'customer' | 'farmer'
}

/** One grow offer and the story of its crop from plan to harvest. */
export default function CropJourneyPage({ audience }: CropJourneyPageProps) {
  const accessToken = useAccessToken()
  const offerId = Number(useParams().offerId)
  const isValidOfferId = Number.isInteger(offerId) && offerId > 0

  const loadJourney = useCallback(async (): Promise<JourneyData> => {
    if (!isValidOfferId) {
      // Nothing is requested for an id that cannot exist; the page says so below.
      throw new Error('invalid grow offer id')
    }
    const [detail, updates] = await Promise.all([
      fetchGrowOfferDetail(offerId),
      fetchCropUpdates(offerId),
    ])
    return { detail, updates }
  }, [offerId, isValidOfferId])
  const { state, reload, updateData } = useAsyncData(loadJourney)

  const [notice, setNotice] = useState<string | null>(null)
  const [completeError, setCompleteError] = useState<string | null>(null)

  const backLink =
    audience === 'farmer'
      ? { to: '/farmer/grow-on-demand', label: 'Back to Grow-On-Demand' }
      : { to: '/customer/grow-offers', label: 'Back to grow offers' }

  async function handlePostUpdate(newUpdate: NewCropUpdate) {
    const update = await postCropUpdate(accessToken, offerId, newUpdate)
    // Posting can move the offer to GROWING or READY, so its details are read again.
    const detail = await fetchGrowOfferDetail(offerId)
    updateData((current) => ({ detail, updates: [...current.updates, update] }))
    setNotice('Your update has been posted and committed customers have been notified.')
  }

  async function handleComplete() {
    setCompleteError(null)
    try {
      const offer = await completeGrowOffer(accessToken, offerId)
      updateData((current) => ({ ...current, detail: { ...current.detail, offer } }))
      setNotice('This grow offer has been marked completed.')
    } catch (error) {
      setCompleteError(describeApiError(error))
    }
  }

  if (!isValidOfferId) {
    return <p className="text-stone-600">This grow offer does not exist.</p>
  }

  return (
    <div className="space-y-6">
      <Link to={backLink.to} className="text-sm font-medium text-green-800 underline underline-offset-4">
        {backLink.label}
      </Link>

      {state.status === 'loading' && (
        <p role="status" className="text-stone-600">
          Loading the crop journey…
        </p>
      )}

      {state.status === 'failed' && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4">
          <p role="alert" className="text-sm text-red-800">
            The crop journey could not be loaded. {state.message}
          </p>
          <button type="button" onClick={reload} className={`mt-3 ${primaryButtonClassName}`}>
            Try again
          </button>
        </div>
      )}

      {state.status === 'loaded' && (
        <JourneyContent
          data={state.data}
          audience={audience}
          notice={notice}
          completeError={completeError}
          onPostUpdate={handlePostUpdate}
          onComplete={handleComplete}
        />
      )}
    </div>
  )
}

type JourneyContentProps = {
  data: JourneyData
  audience: 'customer' | 'farmer'
  notice: string | null
  completeError: string | null
  onPostUpdate: (update: NewCropUpdate) => Promise<void>
  onComplete: () => Promise<void>
}

function JourneyContent({
  data,
  audience,
  notice,
  completeError,
  onPostUpdate,
  onComplete,
}: JourneyContentProps) {
  const { offer, farm } = data.detail
  const unitLabel = productUnitLabels[offer.unit]
  const isClosed = offer.status === 'COMPLETED' || offer.status === 'CANCELLED'
  const stageOptions = selectableStages(offer, data.updates)

  return (
    <>
      <section
        aria-labelledby="journey-offer-heading"
        className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="journey-offer-heading" className="text-xl font-semibold tracking-tight text-stone-900">
            {offer.crop_name}
          </h2>
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${growOfferStatusBadgeClassNames[offer.status]}`}
          >
            {growOfferStatusLabels[offer.status]}
          </span>
        </div>
        <p className="mt-1 text-sm text-stone-600">
          {farm.farm_name}, {farm.city}, {farm.state} · About {formatPrice(offer.estimated_price)} /{' '}
          {unitLabel} · Expected harvest {formatDate(offer.expected_harvest_date)}
        </p>
        <div className="mt-4 sm:w-80">
          <CommitmentProgress offer={offer} />
        </div>
      </section>

      {notice && (
        <p
          role="status"
          className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900"
        >
          {notice}
        </p>
      )}

      {audience === 'farmer' && !isClosed && (
        <section
          aria-labelledby="post-update-heading"
          className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm"
        >
          <h2 id="post-update-heading" className="text-lg font-semibold tracking-tight text-stone-900">
            Post Crop Update
          </h2>
          {offer.status === 'OPEN' && (
            <p className="mt-1 text-sm text-stone-600">
              This offer is not confirmed yet, so only a Planned update can be posted.
            </p>
          )}
          <div className="mt-4">
            <CropUpdateForm
              // Remounting when the choices change selects the first stage still allowed.
              key={stageOptions.map((option) => option.value).join()}
              stageOptions={stageOptions}
              onSubmit={onPostUpdate}
            />
          </div>

          {offer.status === 'READY' && (
            <div className="mt-6 border-t border-stone-200 pt-6">
              <p className="text-sm text-stone-600">
                Once customers have collected their share, close the offer.
              </p>
              {completeError && (
                <p role="alert" className="mt-2 text-sm text-red-800">
                  {completeError}
                </p>
              )}
              <button
                type="button"
                onClick={() => void onComplete()}
                className={`mt-3 ${primaryButtonClassName}`}
              >
                Mark completed
              </button>
            </div>
          )}
        </section>
      )}

      <section aria-labelledby="crop-journey-heading">
        <h2 id="crop-journey-heading" className="text-lg font-semibold tracking-tight text-stone-900">
          Crop journey
        </h2>
        <div className="mt-3">
          <CropJourney updates={data.updates} />
        </div>
      </section>
    </>
  )
}
