import type { GrowOffer } from '../../api/growOffers.ts'
import { productUnitLabels } from '../../data/productOptions.ts'

/**
 * How close a grow offer is to being confirmed, for example
 * "12 / 20 customers committed", with the quantity spoken for underneath.
 */
export default function CommitmentProgress({ offer }: { offer: GrowOffer }) {
  const unitLabel = productUnitLabels[offer.unit]
  const percent = Math.min(100, (offer.committed_customers / offer.minimum_customers) * 100)

  return (
    <div>
      <p className="text-sm font-medium text-stone-900">
        {offer.committed_customers} / {offer.minimum_customers} customers committed
      </p>
      <div
        role="progressbar"
        aria-label={`Commitment progress for ${offer.crop_name}`}
        aria-valuemin={0}
        aria-valuemax={offer.minimum_customers}
        aria-valuenow={Math.min(offer.committed_customers, offer.minimum_customers)}
        className="mt-1.5 h-2 overflow-hidden rounded-full bg-stone-200"
      >
        <div className="h-full rounded-full bg-green-700" style={{ width: `${percent}%` }} />
      </div>
      <p className="mt-1.5 text-xs text-stone-600">
        {offer.committed_quantity} of {offer.expected_quantity} {unitLabel} spoken for
      </p>
    </div>
  )
}
