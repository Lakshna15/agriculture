import { useState } from 'react'
import { Link } from 'react-router'
import type { ProductSearchResult } from '../../api/products.ts'
import type { ProductReservation } from '../../api/reservations.ts'
import { productCategoryLabels, productUnitLabels } from '../../data/productOptions.ts'
import { formatDate, formatDistance, formatPrice, formatTime } from '../../lib/format.ts'
import { primaryButtonClassName } from '../buttonStyles.ts'
import ReserveProductForm from '../reservation/ReserveProductForm.tsx'

function describeFulfilment(farm: ProductSearchResult['farm']): string | null {
  if (farm.pickup_available && farm.delivery_available) {
    return 'Pickup or delivery'
  }
  if (farm.pickup_available) {
    return 'Pickup'
  }
  if (farm.delivery_available) {
    return 'Delivery'
  }
  return null
}

type SearchResultCardProps = {
  result: ProductSearchResult
  /** Called after a reservation is made, so the list can show the reduced stock. */
  onReserved: (reservation: ProductReservation) => void
}

export default function SearchResultCard({ result, onReserved }: SearchResultCardProps) {
  const { product, farm } = result
  const [isReserving, setIsReserving] = useState(false)
  const [latestReservation, setLatestReservation] = useState<ProductReservation | null>(null)

  const unitLabel = productUnitLabels[product.unit]
  const isInStock = result.quantity_available > 0
  const fulfilment = describeFulfilment(farm)

  function handleReserved(reservation: ProductReservation) {
    setIsReserving(false)
    setLatestReservation(reservation)
    onReserved(reservation)
  }

  return (
    <li className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-stone-900">{product.name}</h3>
            {product.organic && (
              <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-900">
                Organic
              </span>
            )}
          </div>
          <p className="mt-0.5 text-sm text-stone-600">{productCategoryLabels[product.category]}</p>
        </div>
        <p className="shrink-0 text-right">
          <span className="text-lg font-semibold text-stone-900">{formatPrice(result.price)}</span>
          <span className="text-sm text-stone-600"> / {unitLabel}</span>
        </p>
      </div>

      {product.description && <p className="mt-3 text-sm text-stone-700">{product.description}</p>}

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-stone-200 pt-4 text-sm sm:grid-cols-4">
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
          {fulfilment && <dd className="text-stone-600">{fulfilment}</dd>}
        </div>
        <div>
          <dt className="text-xs font-medium tracking-wide text-stone-500 uppercase">Available</dt>
          <dd className={`mt-0.5 ${isInStock ? 'text-stone-900' : 'text-red-800'}`}>
            {isInStock ? `${result.quantity_available} ${unitLabel}` : 'Out of stock'}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium tracking-wide text-stone-500 uppercase">Harvested</dt>
          <dd className="mt-0.5 text-stone-900">
            {result.harvest_date ? formatDate(result.harvest_date) : 'Not stated'}
          </dd>
        </div>
      </dl>

      {latestReservation && (
        <p
          role="status"
          className="mt-4 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900"
        >
          Reserved {latestReservation.quantity} {unitLabel} for pickup on{' '}
          {formatDate(latestReservation.pickup_date)} at {formatTime(latestReservation.pickup_time)}.{' '}
          <Link to="/customer/reservations" className="font-medium underline underline-offset-4">
            View my reservations
          </Link>
        </p>
      )}

      {isReserving ? (
        <ReserveProductForm
          productId={product.id}
          unitLabel={unitLabel}
          quantityAvailable={result.quantity_available}
          onReserved={handleReserved}
          onCancel={() => setIsReserving(false)}
        />
      ) : (
        isInStock && (
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              // The label names the product so the buttons are distinguishable to a screen reader.
              aria-label={`Reserve ${product.name}`}
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
