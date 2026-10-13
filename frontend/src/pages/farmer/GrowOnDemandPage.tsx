import { useCallback, useState } from 'react'
import { Link } from 'react-router'
import { fetchLocalDemand, type CropDemand } from '../../api/cropRequests.ts'
import { describeApiError } from '../../api/errors.ts'
import {
  cancelGrowOffer,
  createGrowOffer,
  fetchMyGrowOffers,
  type GrowOffer,
  type NewGrowOffer,
} from '../../api/growOffers.ts'
import type { ProductUnit } from '../../api/products.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import { primaryButtonClassName, secondaryButtonClassName } from '../../components/buttonStyles.ts'
import CommitmentProgress from '../../components/grow/CommitmentProgress.tsx'
import GrowOfferForm from '../../components/grow/GrowOfferForm.tsx'
import { growOfferStatusBadgeClassNames, growOfferStatusLabels } from '../../data/growOptions.ts'
import { productUnitLabels } from '../../data/productOptions.ts'
import { formatDate, formatPrice } from '../../lib/format.ts'
import { useAsyncData } from '../../lib/useAsyncData.ts'

type OfferFormState =
  | { isOpen: false }
  | { isOpen: true; cropName: string; unit: ProductUnit | '' }

function describeCustomers(count: number): string {
  return `${count} ${count === 1 ? 'customer' : 'customers'} interested`
}

/** Shows a quantity without a trailing ".0", so 126 reads as "126" and 9.5 as "9.5". */
function formatQuantity(quantity: number): string {
  return Number.isInteger(quantity) ? String(quantity) : quantity.toFixed(1)
}

function describeDemand(demand: CropDemand): string[] {
  const unitLabel = productUnitLabels[demand.unit]
  const lines: string[] = []
  if (demand.estimated_weekly_quantity > 0) {
    lines.push(
      `${formatQuantity(demand.estimated_weekly_quantity)} ${unitLabel}/week estimated demand`,
    )
  }
  if (demand.one_time_quantity > 0) {
    lines.push(`${demand.one_time_quantity} ${unitLabel} in one-time requests`)
  }
  return lines
}

/** Local demand for crops, and the grow offers the farmer has made in response. */
export default function GrowOnDemandPage() {
  const accessToken = useAccessToken()
  const loadDemand = useCallback(() => fetchLocalDemand(accessToken), [accessToken])
  const loadOffers = useCallback(() => fetchMyGrowOffers(accessToken), [accessToken])
  const { state: demandState, reload: reloadDemand } = useAsyncData(loadDemand)
  const { state: offersState, reload: reloadOffers, updateData: updateOffers } = useAsyncData(loadOffers)

  const [offerForm, setOfferForm] = useState<OfferFormState>({ isOpen: false })
  const [notice, setNotice] = useState<string | null>(null)
  const [offerError, setOfferError] = useState<string | null>(null)

  function openOfferForm(cropName = '', unit: ProductUnit | '' = '') {
    setNotice(null)
    setOfferForm({ isOpen: true, cropName, unit })
  }

  async function handleCreate(newOffer: NewGrowOffer) {
    const offer = await createGrowOffer(accessToken, newOffer)
    updateOffers((offers) => [offer, ...offers])
    setOfferForm({ isOpen: false })
    setNotice(`Your grow offer for ${offer.crop_name} is open for commitments.`)
  }

  async function handleCancel(offer: GrowOffer) {
    setOfferError(null)
    try {
      const cancelledOffer = await cancelGrowOffer(accessToken, offer.id)
      updateOffers((offers) =>
        offers.map((current) => (current.id === cancelledOffer.id ? cancelledOffer : current)),
      )
    } catch (error) {
      setOfferError(describeApiError(error))
    }
  }

  return (
    <div className="space-y-10">
      <section aria-labelledby="local-demand-heading">
        <h2 id="local-demand-heading" className="text-xl font-semibold tracking-tight text-stone-900">
          Local demand
        </h2>
        <p className="mt-1 text-sm text-stone-600">
          Crops that customers within reach of your farm have asked for and cannot find. Figures
          are totals; individual customers and their locations are never shown.
        </p>
        <div className="mt-4">
          {demandState.status === 'loading' && (
            <p role="status" className="text-stone-600">
              Loading local demand…
            </p>
          )}

          {demandState.status === 'failed' && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4">
              <p role="alert" className="text-sm text-red-800">
                Local demand could not be loaded. {demandState.message}
              </p>
              <button type="button" onClick={reloadDemand} className={`mt-3 ${primaryButtonClassName}`}>
                Try again
              </button>
            </div>
          )}

          {demandState.status === 'loaded' && demandState.data.length === 0 && (
            <p className="rounded-xl border border-dashed border-stone-300 bg-white p-6 text-center text-sm text-stone-600">
              No unmet crop requests near your farm right now. Requests appear here as nearby
              customers ask for crops they cannot find.
            </p>
          )}

          {demandState.status === 'loaded' && demandState.data.length > 0 && (
            <ul className="grid gap-3 sm:grid-cols-2">
              {demandState.data.map((demand) => (
                <li
                  key={`${demand.crop_name}-${demand.unit}`}
                  className="rounded-lg border border-stone-200 bg-white p-4"
                >
                  <h3 className="font-semibold text-stone-900">{demand.crop_name}</h3>
                  <p className="mt-1 text-sm font-medium text-stone-900">
                    {describeCustomers(demand.customers_interested)}
                  </p>
                  {describeDemand(demand).map((line) => (
                    <p key={line} className="text-sm text-stone-600">
                      {line}
                    </p>
                  ))}
                  <button
                    type="button"
                    aria-label={`Create grow offer for ${demand.crop_name}`}
                    onClick={() => openOfferForm(demand.crop_name, demand.unit)}
                    className={`mt-4 ${secondaryButtonClassName}`}
                  >
                    Create Grow Offer
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section aria-labelledby="grow-offers-heading">
        <div className="flex items-center justify-between gap-4">
          <h2 id="grow-offers-heading" className="text-xl font-semibold tracking-tight text-stone-900">
            Your grow offers
          </h2>
          {offersState.status === 'loaded' && !offerForm.isOpen && (
            <button type="button" onClick={() => openOfferForm()} className={primaryButtonClassName}>
              Create Grow Offer
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
          {offerError && (
            <p role="alert" className="text-sm text-red-800">
              {offerError}
            </p>
          )}

          {offerForm.isOpen && (
            <GrowOfferForm
              // Remounting when the starting crop changes refills the form from the new demand row.
              key={`${offerForm.cropName}-${offerForm.unit}`}
              initialCropName={offerForm.cropName}
              initialUnit={offerForm.unit}
              onSubmit={handleCreate}
              onCancel={() => setOfferForm({ isOpen: false })}
            />
          )}

          {offersState.status === 'loading' && (
            <p role="status" className="text-stone-600">
              Loading your grow offers…
            </p>
          )}

          {offersState.status === 'failed' && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4">
              <p role="alert" className="text-sm text-red-800">
                Your grow offers could not be loaded. {offersState.message}
              </p>
              <button type="button" onClick={reloadOffers} className={`mt-3 ${primaryButtonClassName}`}>
                Try again
              </button>
            </div>
          )}

          {offersState.status === 'loaded' && offersState.data.length === 0 && !offerForm.isOpen && (
            <p className="rounded-xl border border-dashed border-stone-300 bg-white p-6 text-center text-sm text-stone-600">
              You have not created any grow offers yet. Pick a crop from local demand and offer
              to grow it.
            </p>
          )}

          {offersState.status === 'loaded' && offersState.data.length > 0 && (
            <ul className="space-y-3">
              {offersState.data.map((offer) => {
                const unitLabel = productUnitLabels[offer.unit]
                const canCancel = offer.status === 'OPEN' || offer.status === 'CONFIRMED'
                return (
                  <li key={offer.id} className="rounded-lg border border-stone-200 bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="font-semibold text-stone-900">{offer.crop_name}</h3>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${growOfferStatusBadgeClassNames[offer.status]}`}
                      >
                        {growOfferStatusLabels[offer.status]}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-stone-600">
                      {offer.expected_quantity} {unitLabel} at about{' '}
                      {formatPrice(offer.estimated_price)} / {unitLabel} · Planting{' '}
                      {formatDate(offer.planting_date)} · Harvest{' '}
                      {formatDate(offer.expected_harvest_date)}
                    </p>
                    <div className="mt-3 sm:w-80">
                      <CommitmentProgress offer={offer} />
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Link
                        to={`/farmer/grow-on-demand/${offer.id}`}
                        aria-label={`Crop journey for ${offer.crop_name}`}
                        className={secondaryButtonClassName}
                      >
                        Crop journey
                      </Link>
                      {canCancel && (
                        <button
                          type="button"
                          aria-label={`Cancel grow offer for ${offer.crop_name}`}
                          onClick={() => void handleCancel(offer)}
                          className={secondaryButtonClassName}
                        >
                          Cancel offer
                        </button>
                      )}
                    </div>
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
