import { useState, type FormEvent } from 'react'
import { describeApiError } from '../../api/errors.ts'
import {
  commitToGrowOffer,
  type CropCommitment,
  type GrowOfferSearchResult,
} from '../../api/growOffers.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import { growOfferStatusBadgeClassNames, growOfferStatusLabels } from '../../data/growOptions.ts'
import { productUnitLabels } from '../../data/productOptions.ts'
import { formatDate, formatDistance, formatPrice } from '../../lib/format.ts'
import { WHOLE_NUMBER_PATTERN } from '../../lib/numberInput.ts'
import { primaryButtonClassName, secondaryButtonClassName } from '../buttonStyles.ts'
import FormError from '../FormError.tsx'
import SubmitButton from '../SubmitButton.tsx'
import TextField from '../TextField.tsx'
import CommitmentProgress from './CommitmentProgress.tsx'

type GrowOfferCardProps = {
  result: GrowOfferSearchResult
  /** The signed-in customer's commitment to this offer, if they have already joined it. */
  myCommitment: CropCommitment | undefined
  onJoined: (commitment: CropCommitment) => void
}

/** A grow offer a customer can read about and join. */
export default function GrowOfferCard({ result, myCommitment, onJoined }: GrowOfferCardProps) {
  const { offer, farm } = result
  const accessToken = useAccessToken()
  const [isJoining, setIsJoining] = useState(false)
  const [quantityText, setQuantityText] = useState('1')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const unitLabel = productUnitLabels[offer.unit]
  const quantityRemaining = offer.expected_quantity - offer.committed_quantity
  const canJoin = myCommitment === undefined && quantityRemaining > 0

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const quantity = Number(quantityText)
    const isValidQuantity =
      WHOLE_NUMBER_PATTERN.test(quantityText.trim()) && quantity >= 1 && quantity <= quantityRemaining
    if (!isValidQuantity) {
      setErrorMessage(`Quantity must be a whole number between 1 and ${quantityRemaining}.`)
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      const commitment = await commitToGrowOffer(accessToken, offer.id, quantity)
      setIsJoining(false)
      onJoined(commitment)
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
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-stone-900">{offer.crop_name}</h3>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${growOfferStatusBadgeClassNames[offer.status]}`}
            >
              {growOfferStatusLabels[offer.status]}
            </span>
          </div>
          <p className="mt-0.5 text-sm text-stone-600">
            {farm.farm_name} · {farm.city}, {farm.state} · {formatDistance(result.distance_miles)}
          </p>
        </div>
        <p className="shrink-0 text-right">
          <span className="text-lg font-semibold text-stone-900">
            {formatPrice(offer.estimated_price)}
          </span>
          <span className="text-sm text-stone-600"> / {unitLabel} est.</span>
        </p>
      </div>

      <div className="mt-4 grid gap-4 border-t border-stone-200 pt-4 sm:grid-cols-2">
        <CommitmentProgress offer={offer} />
        <dl className="grid grid-cols-2 gap-x-6 text-sm">
          <div>
            <dt className="text-xs font-medium tracking-wide text-stone-500 uppercase">Planting</dt>
            <dd className="mt-0.5 text-stone-900">{formatDate(offer.planting_date)}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium tracking-wide text-stone-500 uppercase">
              Expected harvest
            </dt>
            <dd className="mt-0.5 text-stone-900">{formatDate(offer.expected_harvest_date)}</dd>
          </div>
        </dl>
      </div>

      {myCommitment && (
        <p
          role="status"
          className="mt-4 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900"
        >
          You committed to {myCommitment.quantity} {unitLabel} of this crop.
        </p>
      )}

      {!myCommitment && quantityRemaining <= 0 && (
        <p className="mt-4 text-sm text-stone-600">The whole expected harvest is spoken for.</p>
      )}

      {isJoining && canJoin && (
        <form onSubmit={handleSubmit} className="mt-4 space-y-4 border-t border-stone-200 pt-4">
          <FormError message={errorMessage} />
          <div className="sm:w-56">
            <TextField
              label={`Quantity (${unitLabel})`}
              name="quantity"
              inputMode="numeric"
              required
              hint={`Up to ${quantityRemaining}. No payment is taken.`}
              value={quantityText}
              onChange={(changeEvent) => setQuantityText(changeEvent.target.value)}
            />
          </div>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={() => setIsJoining(false)}
              disabled={isSubmitting}
              className={secondaryButtonClassName}
            >
              Cancel
            </button>
            <div className="sm:w-48">
              <SubmitButton label="Commit" submittingLabel="Committing…" isSubmitting={isSubmitting} />
            </div>
          </div>
        </form>
      )}

      {!isJoining && canJoin && (
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            // The label names the crop so the buttons are distinguishable to a screen reader.
            aria-label={`Join grow offer for ${offer.crop_name}`}
            onClick={() => setIsJoining(true)}
            className={primaryButtonClassName}
          >
            Join Grow Offer
          </button>
        </div>
      )}
    </li>
  )
}
