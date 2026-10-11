import { useState, type FormEvent } from 'react'
import { describeApiError } from '../../api/errors.ts'
import type { Product, ProductCategory, ProductDetails, ProductUnit } from '../../api/products.ts'
import { productCategoryOptions, productUnitOptions } from '../../data/productOptions.ts'
import { secondaryButtonClassName } from '../buttonStyles.ts'
import CheckboxField from '../CheckboxField.tsx'
import FormError from '../FormError.tsx'
import SelectField from '../SelectField.tsx'
import SubmitButton from '../SubmitButton.tsx'
import TextAreaField from '../TextAreaField.tsx'
import TextField from '../TextField.tsx'

const PRICE_PATTERN = /^\d+(\.\d{1,2})?$/
const WHOLE_NUMBER_PATTERN = /^\d+$/

/** Form state. Numbers stay as text while the user is typing them. */
type ProductFormValues = {
  name: string
  category: ProductCategory | ''
  description: string
  price: string
  unit: ProductUnit | ''
  openingStock: string
  harvestDate: string
  availableFrom: string
  availableUntil: string
  organic: boolean
}

function toFormValues(product: Product | null): ProductFormValues {
  return {
    name: product?.name ?? '',
    category: product?.category ?? '',
    description: product?.description ?? '',
    price: product?.price ?? '',
    unit: product?.unit ?? '',
    openingStock: '0',
    harvestDate: product?.harvest_date ?? '',
    availableFrom: product?.available_from ?? '',
    availableUntil: product?.available_until ?? '',
    organic: product?.organic ?? false,
  }
}

/** Returns a message for the first problem found, or null when the values can be sent. */
function findProblem(values: ProductFormValues, isNewProduct: boolean): string | null {
  if (!PRICE_PATTERN.test(values.price.trim()) || Number(values.price) <= 0) {
    return 'Price must be more than zero with at most two decimal places, for example 4.50.'
  }
  if (isNewProduct && !WHOLE_NUMBER_PATTERN.test(values.openingStock.trim())) {
    return 'Quantity available must be a whole number, zero or more.'
  }
  // ISO dates compare correctly as text.
  if (
    values.availableFrom !== '' &&
    values.availableUntil !== '' &&
    values.availableUntil < values.availableFrom
  ) {
    return 'Available until must not be before available from.'
  }
  return null
}

type ProductFormProps = {
  /** The product being edited, or null when adding one. */
  initialProduct: Product | null
  /** openingStock is only meaningful for a new product; stock is otherwise changed in the list. */
  onSubmit: (details: ProductDetails, openingStock: number) => Promise<void>
  onCancel: () => void
}

export default function ProductForm({ initialProduct, onSubmit, onCancel }: ProductFormProps) {
  const isNewProduct = initialProduct === null
  const [values, setValues] = useState<ProductFormValues>(() => toFormValues(initialProduct))
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function setValue<Field extends keyof ProductFormValues>(
    field: Field,
    value: ProductFormValues[Field],
  ) {
    setValues((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const problem = findProblem(values, isNewProduct)
    if (problem !== null || values.category === '' || values.unit === '') {
      setErrorMessage(problem ?? 'Choose a category and a unit.')
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      await onSubmit(
        {
          name: values.name.trim(),
          category: values.category,
          description: values.description.trim() || null,
          price: values.price.trim(),
          unit: values.unit,
          harvest_date: values.harvestDate || null,
          available_from: values.availableFrom || null,
          available_until: values.availableUntil || null,
          organic: values.organic,
          active: initialProduct?.active ?? true,
        },
        Number(values.openingStock),
      )
    } catch (error) {
      setErrorMessage(describeApiError(error))
      setIsSubmitting(false)
    }
  }

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8">
      <h3 className="text-lg font-semibold tracking-tight text-stone-900">
        {isNewProduct ? 'Add Product' : `Edit ${initialProduct.name}`}
      </h3>
      <form onSubmit={handleSubmit} className="mt-6 space-y-5">
        <FormError message={errorMessage} />

        <div className="grid gap-5 sm:grid-cols-2">
          <TextField
            label="Product name"
            name="name"
            required
            maxLength={120}
            value={values.name}
            onChange={(event) => setValue('name', event.target.value)}
          />
          <SelectField
            label="Category"
            name="category"
            required
            placeholder="Select a category"
            options={productCategoryOptions}
            value={values.category}
            onChange={(event) => setValue('category', event.target.value as ProductCategory | '')}
          />
        </div>

        <TextAreaField
          label="Description"
          name="description"
          rows={2}
          maxLength={2000}
          hint="Optional."
          value={values.description}
          onChange={(event) => setValue('description', event.target.value)}
        />

        <div className={`grid gap-5 ${isNewProduct ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
          <TextField
            label="Price"
            name="price"
            inputMode="decimal"
            required
            hint="In dollars, for example 4.50."
            value={values.price}
            onChange={(event) => setValue('price', event.target.value)}
          />
          <SelectField
            label="Sold by"
            name="unit"
            required
            placeholder="Select a unit"
            options={productUnitOptions}
            value={values.unit}
            onChange={(event) => setValue('unit', event.target.value as ProductUnit | '')}
          />
          {isNewProduct && (
            <TextField
              label="Quantity available"
              name="quantity_available"
              inputMode="numeric"
              required
              hint="Whole units you have to sell now."
              value={values.openingStock}
              onChange={(event) => setValue('openingStock', event.target.value)}
            />
          )}
        </div>

        <div className="grid gap-5 sm:grid-cols-3">
          <TextField
            label="Harvest date"
            name="harvest_date"
            type="date"
            hint="Optional."
            value={values.harvestDate}
            onChange={(event) => setValue('harvestDate', event.target.value)}
          />
          <TextField
            label="Available from"
            name="available_from"
            type="date"
            hint="Optional."
            value={values.availableFrom}
            onChange={(event) => setValue('availableFrom', event.target.value)}
          />
          <TextField
            label="Available until"
            name="available_until"
            type="date"
            hint="Optional."
            value={values.availableUntil}
            onChange={(event) => setValue('availableUntil', event.target.value)}
          />
        </div>

        <CheckboxField
          label="Organic"
          description="Grown without synthetic pesticides or fertilizers."
          checked={values.organic}
          onChange={(checked) => setValue('organic', checked)}
        />

        <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className={secondaryButtonClassName}
          >
            Cancel
          </button>
          <div className="sm:w-44">
            <SubmitButton
              label={isNewProduct ? 'Add Product' : 'Save product'}
              submittingLabel="Saving…"
              isSubmitting={isSubmitting}
            />
          </div>
        </div>
      </form>
    </section>
  )
}
