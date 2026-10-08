import { useState, type FormEvent } from 'react'
import { describeApiError } from '../../api/errors.ts'
import type { Farm, FarmDetails } from '../../api/farms.ts'
import { usStates } from '../../data/usStates.ts'
import CheckboxField from '../CheckboxField.tsx'
import FormError from '../FormError.tsx'
import SelectField from '../SelectField.tsx'
import SubmitButton from '../SubmitButton.tsx'
import TextAreaField from '../TextAreaField.tsx'
import TextField from '../TextField.tsx'

const LATITUDE_LIMIT = 90
const LONGITUDE_LIMIT = 180

const stateOptions = usStates.map((state) => ({ value: state.code, label: state.name }))

/** Form state. Coordinates stay as text while the user is typing them. */
type FarmFormValues = {
  farmName: string
  description: string
  address: string
  city: string
  state: string
  zipCode: string
  latitude: string
  longitude: string
  phone: string
  pickupAvailable: boolean
  deliveryAvailable: boolean
}

function toFormValues(farm: Farm | null): FarmFormValues {
  return {
    farmName: farm?.farm_name ?? '',
    description: farm?.description ?? '',
    address: farm?.address ?? '',
    city: farm?.city ?? '',
    state: farm?.state ?? '',
    zipCode: farm?.zip_code ?? '',
    latitude: farm ? String(farm.latitude) : '',
    longitude: farm ? String(farm.longitude) : '',
    phone: farm?.phone ?? '',
    pickupAvailable: farm?.pickup_available ?? true,
    deliveryAvailable: farm?.delivery_available ?? false,
  }
}

function parseCoordinate(text: string, limit: number): number | null {
  const value = Number(text)
  const isValid = text.trim() !== '' && Number.isFinite(value) && Math.abs(value) <= limit
  return isValid ? value : null
}

type FarmFormProps = {
  title: string
  submitLabel: string
  /** The farm being edited, or null when creating one. */
  initialFarm: Farm | null
  onSubmit: (details: FarmDetails) => Promise<void>
  onCancel: () => void
}

export default function FarmForm({
  title,
  submitLabel,
  initialFarm,
  onSubmit,
  onCancel,
}: FarmFormProps) {
  const [values, setValues] = useState<FarmFormValues>(() => toFormValues(initialFarm))
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function setValue<Field extends keyof FarmFormValues>(field: Field, value: FarmFormValues[Field]) {
    setValues((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const latitude = parseCoordinate(values.latitude, LATITUDE_LIMIT)
    if (latitude === null) {
      setErrorMessage(`Latitude must be a number between -${LATITUDE_LIMIT} and ${LATITUDE_LIMIT}.`)
      return
    }
    const longitude = parseCoordinate(values.longitude, LONGITUDE_LIMIT)
    if (longitude === null) {
      setErrorMessage(
        `Longitude must be a number between -${LONGITUDE_LIMIT} and ${LONGITUDE_LIMIT}.`,
      )
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      await onSubmit({
        farm_name: values.farmName.trim(),
        description: values.description.trim() || null,
        address: values.address.trim(),
        city: values.city.trim(),
        state: values.state,
        zip_code: values.zipCode.trim(),
        latitude,
        longitude,
        phone: values.phone.trim() || null,
        pickup_available: values.pickupAvailable,
        delivery_available: values.deliveryAvailable,
      })
    } catch (error) {
      setErrorMessage(describeApiError(error))
      setIsSubmitting(false)
    }
  }

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8">
      <h2 className="text-xl font-semibold tracking-tight text-stone-900">{title}</h2>
      <form onSubmit={handleSubmit} className="mt-6 space-y-5">
        <FormError message={errorMessage} />

        <TextField
          label="Farm name"
          name="farm_name"
          required
          maxLength={120}
          value={values.farmName}
          onChange={(event) => setValue('farmName', event.target.value)}
        />
        <TextAreaField
          label="Description"
          name="description"
          rows={3}
          maxLength={2000}
          hint="Optional. Tell customers what you grow and how you farm."
          value={values.description}
          onChange={(event) => setValue('description', event.target.value)}
        />
        <TextField
          label="Street address"
          name="address"
          autoComplete="street-address"
          required
          maxLength={200}
          value={values.address}
          onChange={(event) => setValue('address', event.target.value)}
        />

        <div className="grid gap-5 sm:grid-cols-3">
          <TextField
            label="City"
            name="city"
            autoComplete="address-level2"
            required
            maxLength={100}
            value={values.city}
            onChange={(event) => setValue('city', event.target.value)}
          />
          <SelectField
            label="State"
            name="state"
            autoComplete="address-level1"
            required
            placeholder="Select a state"
            options={stateOptions}
            value={values.state}
            onChange={(event) => setValue('state', event.target.value)}
          />
          <TextField
            label="ZIP code"
            name="zip_code"
            autoComplete="postal-code"
            inputMode="numeric"
            required
            pattern="\d{5}(-\d{4})?"
            hint="Five digits, or ZIP+4."
            value={values.zipCode}
            onChange={(event) => setValue('zipCode', event.target.value)}
          />
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <TextField
            label="Latitude"
            name="latitude"
            inputMode="decimal"
            required
            hint="Decimal degrees, for example 35.2271."
            value={values.latitude}
            onChange={(event) => setValue('latitude', event.target.value)}
          />
          <TextField
            label="Longitude"
            name="longitude"
            inputMode="decimal"
            required
            hint="Decimal degrees, for example -80.8431. West is negative."
            value={values.longitude}
            onChange={(event) => setValue('longitude', event.target.value)}
          />
        </div>

        <TextField
          label="Phone"
          name="phone"
          type="tel"
          autoComplete="tel"
          maxLength={30}
          hint="Optional."
          value={values.phone}
          onChange={(event) => setValue('phone', event.target.value)}
        />

        <fieldset>
          <legend className="text-sm font-medium text-stone-800">How customers get their order</legend>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            <CheckboxField
              label="Pickup available"
              description="Customers collect from the farm."
              checked={values.pickupAvailable}
              onChange={(checked) => setValue('pickupAvailable', checked)}
            />
            <CheckboxField
              label="Delivery available"
              description="You deliver to customers."
              checked={values.deliveryAvailable}
              onChange={(checked) => setValue('deliveryAvailable', checked)}
            />
          </div>
        </fieldset>

        <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="rounded-md border border-stone-300 bg-white px-4 py-2.5 text-sm font-semibold text-stone-800 shadow-sm transition-colors hover:bg-stone-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancel
          </button>
          <div className="sm:w-44">
            <SubmitButton label={submitLabel} submittingLabel="Saving…" isSubmitting={isSubmitting} />
          </div>
        </div>
      </form>
    </section>
  )
}
