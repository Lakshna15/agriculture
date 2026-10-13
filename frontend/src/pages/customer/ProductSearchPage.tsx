import { useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { describeApiError } from '../../api/errors.ts'
import {
  searchProducts,
  type ProductCategory,
  type ProductSearchResult,
  type ProductSearchSort,
} from '../../api/products.ts'
import type { ProductReservation } from '../../api/reservations.ts'
import { primaryButtonClassName } from '../../components/buttonStyles.ts'
import CheckboxField from '../../components/CheckboxField.tsx'
import FormError from '../../components/FormError.tsx'
import LocationFields from '../../components/search/LocationFields.tsx'
import SearchResultCard from '../../components/search/SearchResultCard.tsx'
import SelectField from '../../components/SelectField.tsx'
import SubmitButton from '../../components/SubmitButton.tsx'
import TextField from '../../components/TextField.tsx'
import {
  DEFAULT_SEARCH_RADIUS_MILES,
  productCategoryOptions,
  searchRadiusMilesOptions,
  searchSortOptions,
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

const radiusOptions = searchRadiusMilesOptions.map((miles) => ({
  value: String(miles),
  label: `${miles} miles`,
}))

type SearchFormValues = {
  query: string
  radiusMiles: string
  category: ProductCategory | ''
  availableOnly: boolean
  sort: ProductSearchSort
}

type SearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  /** query and radiusMiles describe the search that produced these results. */
  | { status: 'loaded'; results: ProductSearchResult[]; query: string; radiusMiles: number }

function describeResultCount(count: number, radiusMiles: number): string {
  const noun = count === 1 ? 'product' : 'products'
  return `${count} ${noun} within ${radiusMiles} miles`
}

/** Search for products on nearby farms and reserve them. */
export default function ProductSearchPage() {
  const [location, setLocation] = useState<SearchLocation>(readSearchLocation)
  const [values, setValues] = useState<SearchFormValues>({
    query: '',
    radiusMiles: String(DEFAULT_SEARCH_RADIUS_MILES),
    category: '',
    availableOnly: true,
    sort: 'distance',
  })
  const [formError, setFormError] = useState<string | null>(null)
  const [searchState, setSearchState] = useState<SearchState>({ status: 'idle' })
  // Identifies the newest search so that a slower, older response cannot replace its results.
  const latestSearchNumber = useRef(0)

  function setValue<Field extends keyof SearchFormValues>(
    field: Field,
    value: SearchFormValues[Field],
  ) {
    setValues((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

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
    setSearchState({ status: 'loading' })
    storeSearchLocation(location)
    const searchNumber = ++latestSearchNumber.current
    const query = values.query.trim()
    const radiusMiles = Number(values.radiusMiles)

    try {
      const results = await searchProducts({
        query,
        category: values.category,
        latitude,
        longitude,
        radiusMiles,
        availableOnly: values.availableOnly,
        sort: values.sort,
      })
      if (searchNumber === latestSearchNumber.current) {
        setSearchState({ status: 'loaded', results, query, radiusMiles })
      }
    } catch (error) {
      if (searchNumber === latestSearchNumber.current) {
        setSearchState({ status: 'failed', message: describeApiError(error) })
      }
    }
  }

  function showReducedStock(reservation: ProductReservation) {
    setSearchState((current) => {
      if (current.status !== 'loaded') {
        return current
      }
      const results = current.results.map((result) =>
        result.product.id === reservation.product.id
          ? { ...result, quantity_available: result.quantity_available - reservation.quantity }
          : result,
      )
      return { ...current, results }
    })
  }

  return (
    <>
      <section
        aria-labelledby="search-heading"
        className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <h2 id="search-heading" className="text-xl font-semibold tracking-tight text-stone-900">
          Search nearby products
        </h2>
        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          <FormError message={formError} />

          <TextField
            label="Search term"
            name="query"
            type="search"
            maxLength={100}
            placeholder="Tomatoes, eggs, honey…"
            hint="Optional. Leave empty to see everything nearby."
            value={values.query}
            onChange={(event) => setValue('query', event.target.value)}
          />

          <LocationFields location={location} onChange={setLocation} />

          <div className="grid gap-5 sm:grid-cols-3">
            <SelectField
              label="Radius"
              name="radius_miles"
              options={radiusOptions}
              value={values.radiusMiles}
              onChange={(event) => setValue('radiusMiles', event.target.value)}
            />
            <SelectField
              label="Category"
              name="category"
              placeholder="All categories"
              options={productCategoryOptions}
              value={values.category}
              onChange={(event) => setValue('category', event.target.value as ProductCategory | '')}
            />
            <SelectField
              label="Sort"
              name="sort"
              options={searchSortOptions}
              value={values.sort}
              onChange={(event) => setValue('sort', event.target.value as ProductSearchSort)}
            />
          </div>

          <CheckboxField
            label="Available now only"
            description="Hide products that are out of stock or out of season."
            checked={values.availableOnly}
            onChange={(checked) => setValue('availableOnly', checked)}
          />

          <div className="sm:w-44">
            <SubmitButton
              label="Search"
              submittingLabel="Searching…"
              isSubmitting={searchState.status === 'loading'}
            />
          </div>
        </form>
      </section>

      <section aria-labelledby="results-heading" aria-live="polite" className="mt-8">
        <h2 id="results-heading" className="sr-only">
          Search results
        </h2>

        {searchState.status === 'idle' && (
          <p className="text-center text-stone-600">
            Enter your location and choose a radius to see what nearby farms are offering.
          </p>
        )}

        {searchState.status === 'loading' && (
          <p role="status" className="text-center text-stone-600">
            Searching nearby farms…
          </p>
        )}

        {searchState.status === 'failed' && (
          <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            The search could not be completed. {searchState.message}
          </p>
        )}

        {searchState.status === 'loaded' && searchState.results.length === 0 && (
          <div className="rounded-xl border border-dashed border-stone-300 bg-white p-8 text-center">
            <p className="font-semibold text-stone-900">
              {searchState.query
                ? 'No nearby farms currently have this crop.'
                : `No products were found within ${searchState.radiusMiles} miles.`}
            </p>
            <p className="mx-auto mt-2 max-w-md text-sm text-stone-600">
              Try a wider radius, a different search term, or include products that are not
              available right now.
            </p>
            <div className="mx-auto mt-6 max-w-md border-t border-stone-200 pt-6">
              <p className="font-semibold text-stone-900">{"Can't find this crop nearby?"}</p>
              <p className="mt-1 text-sm text-stone-600">Request it from local farmers.</p>
              <Link
                to="/customer/crop-requests"
                // The crop request form starts with what the customer just searched for.
                state={{ cropName: searchState.query }}
                className={`mt-4 inline-block ${primaryButtonClassName}`}
              >
                Request this crop
              </Link>
            </div>
          </div>
        )}

        {searchState.status === 'loaded' && searchState.results.length > 0 && (
          <>
            <p className="text-sm font-medium text-stone-700">
              {describeResultCount(searchState.results.length, searchState.radiusMiles)}
            </p>
            <ul className="mt-3 space-y-3">
              {searchState.results.map((result) => (
                <SearchResultCard
                  key={result.product.id}
                  result={result}
                  onReserved={showReducedStock}
                />
              ))}
            </ul>
            <p className="mt-6 text-center text-sm text-stone-600">
              Not what you were looking for?{' '}
              <Link
                to="/customer/crop-requests"
                state={{ cropName: searchState.query }}
                className="font-medium text-green-800 underline underline-offset-4"
              >
                Request a crop from local farmers
              </Link>
            </p>
          </>
        )}
      </section>
    </>
  )
}
