import { useState, type FormEvent } from 'react'
import { describeApiError } from '../../api/errors.ts'
import type { NewGrowOffer } from '../../api/growOffers.ts'
import type { ProductUnit } from '../../api/products.ts'
import { productUnitOptions } from '../../data/productOptions.ts'
import { todayAsIsoDate } from '../../lib/format.ts'
import { secondaryButtonClassName } from '../buttonStyles.ts'
import FormError from '../FormError.tsx'
import SelectField from '../SelectField.tsx'
import SubmitButton from '../SubmitButton.tsx'
import TextField from '../TextField.tsx'

const PRICE_PATTERN = /^\d+(\.\d{1,2})?$/
const WHOLE_NUMBER_PATTERN = /^\d+$/

/** Form state. Numbers stay as text while the user is typing them. */
type GrowOfferFormValues = {
  cropName: string
  expectedQuantity: string
  unit: ProductUnit | ''
  estimatedPrice: string
  plantingDate: string
  expectedHarvestDate: string
  minimumCustomers: string
}

function isWholeNumberOfAtLeastOne(text: string): boolean {
  return WHOLE_NUMBER_PATTERN.test(text.trim()) && Number(text) >= 1
}

/** Returns a message for the first problem found, or null when the values can be sent. */
function findProblem(values: GrowOfferFormValues, today: string): string | null {
  if (values.cropName.trim().length < 2) {
    return 'Enter the name of the crop you would grow.'
  }
  if (!isWholeNumberOfAtLeastOne(values.expectedQuantity)) {
    return 'Expected quantity must be a whole number of at least 1.'
  }
  if (!PRICE_PATTERN.test(values.estimatedPrice.trim()) || Number(values.estimatedPrice) <= 0) {
    return 'Estimated price must be more than zero with at most two decimal places, for example 3.50.'
  }
  if (values.plantingDate === '' || values.expectedHarvestDate === '') {
    return 'Choose a planting date and an expected harvest date.'
  }
  // ISO dates compare correctly as text.
  if (values.expectedHarvestDate < values.plantingDate) {
    return 'The expected harvest date must not be before the planting date.'
  }
  if (values.expectedHarvestDate < today) {
    return 'The expected harvest date must be today or later.'
  }
  if (!isWholeNumberOfAtLeastOne(values.minimumCustomers)) {
    return 'Minimum customers must be a whole number of at least 1.'
  }
  return null
}

type GrowOfferFormProps = {
  /** Filled in when the farmer starts from a row of local demand. */
  initialCropName: string
  initialUnit: ProductUnit | ''
  onSubmit: (offer: NewGrowOffer) => Promise<void>
  onCancel: () => void
}

export default function GrowOfferForm({
  initialCropName,
  initialUnit,
  onSubmit,
  onCancel,
}: GrowOfferFormProps) {
  const today = todayAsIsoDate()
  const [values, setValues] = useState<GrowOfferFormValues>({
    cropName: initialCropName,
    expectedQuantity: '',
    unit: initialUnit,
    estimatedPrice: '',
    plantingDate: '',
    expectedHarvestDate: '',
    minimumCustomers: '',
  })
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function setValue<Field extends keyof GrowOfferFormValues>(
    field: Field,
    value: GrowOfferFormValues[Field],
  ) {
    setValues((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const problem = findProblem(values, today)
    if (problem !== null || values.unit === '') {
      setErrorMessage(problem ?? 'Choose a unit.')
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      await onSubmit({
        crop_name: values.cropName.trim(),
        expected_quantity: Number(values.expectedQuantity),
        unit: values.unit,
        estimated_price: values.estimatedPrice.trim(),
        planting_date: values.plantingDate,
        expected_harvest_date: values.expectedHarvestDate,
        minimum_customers: Number(values.minimumCustomers),
      })
    } catch (error) {
      setErrorMessage(describeApiError(error))
      setIsSubmitting(false)
    }
  }

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8">
      <h3 className="text-lg font-semibold tracking-tight text-stone-900">Create Grow Offer</h3>
      <p className="mt-1 text-sm text-stone-600">
        Offer to grow a crop if enough customers commit. The offer is confirmed automatically
        once it reaches the minimum number of customers.
      </p>
      <form onSubmit={handleSubmit} className="mt-6 space-y-5">
        <FormError message={errorMessage} />

        <TextField
          label="Crop"
          name="crop_name"
          required
          maxLength={80}
          value={values.cropName}
          onChange={(event) => setValue('cropName', event.target.value)}
        />

        <div className="grid gap-5 sm:grid-cols-3">
          <TextField
            label="Expected quantity"
            name="expected_quantity"
            inputMode="numeric"
            required
            hint="The harvest you expect in total."
            value={values.expectedQuantity}
            onChange={(event) => setValue('expectedQuantity', event.target.value)}
          />
          <SelectField
            label="Unit"
            name="unit"
            required
            placeholder="Select a unit"
            options={productUnitOptions}
            value={values.unit}
            onChange={(event) => setValue('unit', event.target.value as ProductUnit | '')}
          />
          <TextField
            label="Estimated price"
            name="estimated_price"
            inputMode="decimal"
            required
            hint="Per unit, in dollars."
            value={values.estimatedPrice}
            onChange={(event) => setValue('estimatedPrice', event.target.value)}
          />
        </div>

        <div className="grid gap-5 sm:grid-cols-3">
          <TextField
            label="Planting date"
            name="planting_date"
            type="date"
            required
            value={values.plantingDate}
            onChange={(event) => setValue('plantingDate', event.target.value)}
          />
          <TextField
            label="Expected harvest date"
            name="expected_harvest_date"
            type="date"
            required
            value={values.expectedHarvestDate}
            onChange={(event) => setValue('expectedHarvestDate', event.target.value)}
          />
          <TextField
            label="Minimum customers"
            name="minimum_customers"
            inputMode="numeric"
            required
            hint="Commitments needed to go ahead."
            value={values.minimumCustomers}
            onChange={(event) => setValue('minimumCustomers', event.target.value)}
          />
        </div>

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
            <SubmitButton label="Create offer" submittingLabel="Saving…" isSubmitting={isSubmitting} />
          </div>
        </div>
      </form>
    </section>
  )
}
