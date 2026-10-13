import { useCallback, useState, type FormEvent } from 'react'
import { useLocation } from 'react-router'
import {
  cancelCropRequest,
  createCropRequest,
  fetchMyCropRequests,
  type CropRequest,
  type RequestFrequency,
  type Season,
} from '../../api/cropRequests.ts'
import { describeApiError } from '../../api/errors.ts'
import type { ProductUnit } from '../../api/products.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import { primaryButtonClassName, secondaryButtonClassName } from '../../components/buttonStyles.ts'
import FormError from '../../components/FormError.tsx'
import LocationFields from '../../components/search/LocationFields.tsx'
import SelectField from '../../components/SelectField.tsx'
import SubmitButton from '../../components/SubmitButton.tsx'
import TextAreaField from '../../components/TextAreaField.tsx'
import TextField from '../../components/TextField.tsx'
import {
  requestFrequencyLabels,
  requestFrequencyOptions,
  seasonLabels,
  seasonOptions,
} from '../../data/growOptions.ts'
import {
  DEFAULT_SEARCH_RADIUS_MILES,
  productUnitLabels,
  productUnitOptions,
  searchRadiusMilesOptions,
} from '../../data/productOptions.ts'
import {
  LATITUDE_LIMIT,
  LONGITUDE_LIMIT,
  latitudeErrorMessage,
  longitudeErrorMessage,
  parseCoordinate,
} from '../../lib/coordinates.ts'
import {
  readSearchLocation,
  storeSearchLocation,
  type SearchLocation,
} from '../../lib/searchLocation.ts'
import { useAsyncData } from '../../lib/useAsyncData.ts'

const WHOLE_NUMBER_PATTERN = /^\d+$/

const radiusOptions = searchRadiusMilesOptions.map((miles) => ({
  value: String(miles),
  label: `${miles} miles`,
}))

type CropRequestFormValues = {
  cropName: string
  quantity: string
  unit: ProductUnit | ''
  frequency: RequestFrequency
  radiusMiles: string
  preferredSeason: Season | ''
  notes: string
}

/** The crop a customer searched for and could not find, passed along by the search page. */
function readCropNameFromNavigation(state: unknown): string {
  if (typeof state === 'object' && state !== null && 'cropName' in state) {
    return typeof state.cropName === 'string' ? state.cropName : ''
  }
  return ''
}

function describeRequest(request: CropRequest): string[] {
  const unitLabel = productUnitLabels[request.unit]
  return [
    `${request.quantity} ${unitLabel} ${requestFrequencyLabels[request.frequency]}`,
    `From farms within ${request.radius_miles} miles`,
    ...(request.preferred_season ? [`Preferred season: ${seasonLabels[request.preferred_season]}`] : []),
    ...(request.notes ? [request.notes] : []),
  ]
}

function describeStatus(request: CropRequest): { label: string; className: string } {
  if (request.status === 'CANCELLED') {
    return { label: 'Cancelled', className: 'bg-red-100 text-red-900' }
  }
  if (request.covered_by_commitment) {
    return { label: 'Covered by a grow offer you joined', className: 'bg-green-100 text-green-900' }
  }
  return { label: 'Open', className: 'bg-amber-100 text-amber-900' }
}

/** Ask nearby farmers to grow a crop, and see the requests already made. */
export default function CropRequestsPage() {
  const accessToken = useAccessToken()
  const navigation = useLocation()
  const loadRequests = useCallback(() => fetchMyCropRequests(accessToken), [accessToken])
  const { state: requestsState, reload, updateData } = useAsyncData(loadRequests)

  const [location, setLocation] = useState<SearchLocation>(readSearchLocation)
  const [values, setValues] = useState<CropRequestFormValues>(() => ({
    cropName: readCropNameFromNavigation(navigation.state),
    quantity: '',
    unit: '',
    frequency: 'WEEKLY',
    radiusMiles: String(DEFAULT_SEARCH_RADIUS_MILES),
    preferredSeason: '',
    notes: '',
  }))
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [listError, setListError] = useState<string | null>(null)

  function setValue<Field extends keyof CropRequestFormValues>(
    field: Field,
    value: CropRequestFormValues[Field],
  ) {
    setValues((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setNotice(null)

    if (values.cropName.trim().length < 2) {
      setFormError('Enter the name of the crop you are looking for.')
      return
    }
    if (!WHOLE_NUMBER_PATTERN.test(values.quantity.trim()) || Number(values.quantity) < 1) {
      setFormError('Quantity must be a whole number of at least 1.')
      return
    }
    if (values.unit === '') {
      setFormError('Choose a unit.')
      return
    }
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
    setIsSubmitting(true)
    storeSearchLocation(location)
    try {
      const request = await createCropRequest(accessToken, {
        crop_name: values.cropName.trim(),
        quantity: Number(values.quantity),
        unit: values.unit,
        frequency: values.frequency,
        latitude,
        longitude,
        radius_miles: Number(values.radiusMiles),
        preferred_season: values.preferredSeason || null,
        notes: values.notes.trim() || null,
      })
      updateData((requests) => [request, ...requests])
      setNotice(
        `Your request for ${request.crop_name} has been sent. Nearby farmers will see it as part of local demand.`,
      )
      setValues((current) => ({ ...current, cropName: '', quantity: '', notes: '' }))
    } catch (error) {
      setFormError(describeApiError(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleCancel(request: CropRequest) {
    setListError(null)
    try {
      const cancelledRequest = await cancelCropRequest(accessToken, request.id)
      updateData((requests) =>
        requests.map((current) => (current.id === cancelledRequest.id ? cancelledRequest : current)),
      )
    } catch (error) {
      setListError(describeApiError(error))
    }
  }

  return (
    <div className="space-y-10">
      <section
        aria-labelledby="request-crop-heading"
        className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <h2 id="request-crop-heading" className="text-xl font-semibold tracking-tight text-stone-900">
          Request a crop
        </h2>
        <p className="mt-1 text-sm text-stone-600">
          Tell nearby farmers what you would buy if they grew it. Farmers see how many people
          want a crop and how much, never who asked or where you are.
        </p>
        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          <FormError message={formError} />
          {notice && (
            <p
              role="status"
              className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900"
            >
              {notice}
            </p>
          )}

          <TextField
            label="Crop"
            name="crop_name"
            required
            maxLength={80}
            placeholder="Okra, sweet corn, bok choy…"
            value={values.cropName}
            onChange={(event) => setValue('cropName', event.target.value)}
          />

          <div className="grid gap-5 sm:grid-cols-3">
            <TextField
              label="Quantity"
              name="quantity"
              inputMode="numeric"
              required
              value={values.quantity}
              onChange={(event) => setValue('quantity', event.target.value)}
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
            <SelectField
              label="How often"
              name="frequency"
              options={requestFrequencyOptions}
              value={values.frequency}
              onChange={(event) => setValue('frequency', event.target.value as RequestFrequency)}
            />
          </div>

          <LocationFields location={location} onChange={setLocation} />

          <div className="grid gap-5 sm:grid-cols-2">
            <SelectField
              label="How far you would travel"
              name="radius_miles"
              options={radiusOptions}
              value={values.radiusMiles}
              onChange={(event) => setValue('radiusMiles', event.target.value)}
            />
            <SelectField
              label="Preferred season"
              name="preferred_season"
              placeholder="Any season"
              options={seasonOptions}
              value={values.preferredSeason}
              onChange={(event) => setValue('preferredSeason', event.target.value as Season | '')}
            />
          </div>

          <TextAreaField
            label="Notes"
            name="notes"
            rows={2}
            maxLength={1000}
            hint="Optional. Only you can see these."
            value={values.notes}
            onChange={(event) => setValue('notes', event.target.value)}
          />

          <div className="sm:w-48">
            <SubmitButton
              label="Request this crop"
              submittingLabel="Sending…"
              isSubmitting={isSubmitting}
            />
          </div>
        </form>
      </section>

      <section aria-labelledby="my-crop-requests-heading">
        <h2
          id="my-crop-requests-heading"
          className="text-xl font-semibold tracking-tight text-stone-900"
        >
          My crop requests
        </h2>
        <div className="mt-4">
          {listError && (
            <p role="alert" className="mb-3 text-sm text-red-800">
              {listError}
            </p>
          )}

          {requestsState.status === 'loading' && (
            <p role="status" className="text-stone-600">
              Loading your crop requests…
            </p>
          )}

          {requestsState.status === 'failed' && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4">
              <p role="alert" className="text-sm text-red-800">
                Your crop requests could not be loaded. {requestsState.message}
              </p>
              <button type="button" onClick={reload} className={`mt-3 ${primaryButtonClassName}`}>
                Try again
              </button>
            </div>
          )}

          {requestsState.status === 'loaded' && requestsState.data.length === 0 && (
            <p className="rounded-xl border border-dashed border-stone-300 bg-white p-6 text-center text-sm text-stone-600">
              You have not requested any crops yet. When a search comes up empty, ask local
              farmers to grow what you were looking for.
            </p>
          )}

          {requestsState.status === 'loaded' && requestsState.data.length > 0 && (
            <ul className="space-y-3">
              {requestsState.data.map((request) => {
                const status = describeStatus(request)
                return (
                  <li key={request.id} className="rounded-lg border border-stone-200 bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="font-semibold text-stone-900">{request.crop_name}</h3>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${status.className}`}
                      >
                        {status.label}
                      </span>
                    </div>
                    <ul className="mt-1 space-y-0.5 text-sm text-stone-600">
                      {describeRequest(request).map((fact) => (
                        <li key={fact}>{fact}</li>
                      ))}
                    </ul>
                    {request.status === 'OPEN' && (
                      <button
                        type="button"
                        aria-label={`Cancel request for ${request.crop_name}`}
                        onClick={() => void handleCancel(request)}
                        className={`mt-4 ${secondaryButtonClassName}`}
                      >
                        Cancel request
                      </button>
                    )}
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
