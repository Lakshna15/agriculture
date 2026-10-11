import { useState, type FormEvent } from 'react'
import { describeApiError } from '../../api/errors.ts'
import type { Product } from '../../api/products.ts'
import { productCategoryLabels, productUnitLabels } from '../../data/productOptions.ts'
import { formatDate, formatPrice } from '../../lib/format.ts'
import { secondaryButtonClassName } from '../buttonStyles.ts'
import { fieldControlClassName } from '../fieldStyles.ts'

const WHOLE_NUMBER_PATTERN = /^\d+$/

function describeAvailability(product: Product): string | null {
  if (product.available_from && product.available_until) {
    return `Available ${formatDate(product.available_from)} to ${formatDate(product.available_until)}`
  }
  if (product.available_from) {
    return `Available from ${formatDate(product.available_from)}`
  }
  if (product.available_until) {
    return `Available until ${formatDate(product.available_until)}`
  }
  return null
}

type ProductListItemProps = {
  product: Product
  onEdit: () => void
  onUpdateStock: (quantityAvailable: number) => Promise<void>
  onSetActive: (active: boolean) => Promise<void>
}

export default function ProductListItem({
  product,
  onEdit,
  onUpdateStock,
  onSetActive,
}: ProductListItemProps) {
  const [stockText, setStockText] = useState(String(product.quantity_available))
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isBusy, setIsBusy] = useState(false)

  const unitLabel = productUnitLabels[product.unit]
  const activeToggleLabel = product.active ? 'Deactivate' : 'Activate'
  const facts = [
    productCategoryLabels[product.category],
    `${formatPrice(product.price)} / ${unitLabel}`,
    product.harvest_date ? `Harvested ${formatDate(product.harvest_date)}` : null,
    describeAvailability(product),
  ].filter((fact) => fact !== null)

  async function run(action: () => Promise<void>) {
    setErrorMessage(null)
    setIsBusy(true)
    try {
      await action()
    } catch (error) {
      setErrorMessage(describeApiError(error))
    } finally {
      setIsBusy(false)
    }
  }

  function handleStockSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!WHOLE_NUMBER_PATTERN.test(stockText.trim())) {
      setErrorMessage('Stock must be a whole number, zero or more.')
      return
    }
    void run(() => onUpdateStock(Number(stockText)))
  }

  return (
    <li className="rounded-lg border border-stone-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold text-stone-900">{product.name}</h3>
        {product.organic && (
          <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-900">
            Organic
          </span>
        )}
        {!product.active && (
          <span className="rounded-full bg-stone-200 px-2 py-0.5 text-xs font-medium text-stone-700">
            Hidden from customers
          </span>
        )}
      </div>
      <p className="mt-1 text-sm text-stone-600">{facts.join(' · ')}</p>
      <p className="mt-1 text-sm text-stone-900">
        {product.quantity_available} {unitLabel} in stock
      </p>

      {errorMessage && (
        <p role="alert" className="mt-3 text-sm text-red-800">
          {errorMessage}
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
        <form onSubmit={handleStockSubmit} className="flex items-end gap-2">
          <div className="w-28">
            <label
              htmlFor={`stock-${product.id}`}
              className="block text-xs font-medium text-stone-700"
            >
              Stock for {product.name}
            </label>
            <input
              id={`stock-${product.id}`}
              inputMode="numeric"
              value={stockText}
              onChange={(event) => setStockText(event.target.value)}
              className={fieldControlClassName}
            />
          </div>
          <button type="submit" disabled={isBusy} className={secondaryButtonClassName}>
            Update stock
          </button>
        </form>

        <div className="flex gap-2">
          {/* The labels name the product so the buttons are distinguishable to a screen reader. */}
          <button
            type="button"
            aria-label={`Edit ${product.name}`}
            onClick={onEdit}
            disabled={isBusy}
            className={secondaryButtonClassName}
          >
            Edit
          </button>
          <button
            type="button"
            aria-label={`${activeToggleLabel} ${product.name}`}
            onClick={() => void run(() => onSetActive(!product.active))}
            disabled={isBusy}
            className={secondaryButtonClassName}
          >
            {activeToggleLabel}
          </button>
        </div>
      </div>
    </li>
  )
}
