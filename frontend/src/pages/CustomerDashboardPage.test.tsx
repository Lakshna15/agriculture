import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import type { ProductSearchResult } from '../api/products.ts'
import { buildSearchResult, buildUser, installFakeApi } from '../test/fakeApi.ts'
import { renderApp } from '../test/renderApp.tsx'

const customer = buildUser({ id: 1, name: 'Ana Grower', email: 'ana@example.com', role: 'CUSTOMER' })

function openDashboard(searchResults: ProductSearchResult[] = []) {
  const api = installFakeApi({
    accounts: [{ user: customer, password: 'correct-horse-battery' }],
    searchResults,
  })
  api.signIn(customer)
  renderApp('/customer')
  return api
}

async function enterLocation(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Latitude'), '35.2271')
  await user.type(screen.getByLabelText('Longitude'), '-80.8431')
}

describe('search form', () => {
  it('invites the customer to search before anything has been searched', async () => {
    openDashboard()

    expect(
      await screen.findByText(/Enter your location and choose a radius/),
    ).toBeInTheDocument()
  })

  it('offers the suggested radius values with 25 miles selected', async () => {
    openDashboard()

    const radius = await screen.findByLabelText('Radius')
    const optionLabels = within(radius)
      .getAllByRole('option')
      .map((option) => option.textContent)
    expect(optionLabels).toEqual(['5 miles', '10 miles', '25 miles', '50 miles', '100 miles'])
    expect(radius).toHaveValue('25')
  })

  it('searches with the defaults when only a location is given', async () => {
    const api = openDashboard()
    const user = userEvent.setup()

    await enterLocation(user)
    await user.click(screen.getByRole('button', { name: 'Search' }))

    await screen.findByText('No products were found within 25 miles.')
    expect(api.searches).toEqual([
      {
        latitude: '35.2271',
        longitude: '-80.8431',
        radius_miles: '25',
        available_only: 'true',
        sort: 'distance',
      },
    ])
  })

  it('sends every chosen criterion', async () => {
    const api = openDashboard()
    const user = userEvent.setup()

    await enterLocation(user)
    await user.type(screen.getByLabelText('Search term'), '  strawberries ')
    await user.selectOptions(screen.getByLabelText('Radius'), '10 miles')
    await user.selectOptions(screen.getByLabelText('Category'), 'Fruits')
    await user.selectOptions(screen.getByLabelText('Sort'), 'Lowest price first')
    await user.click(screen.getByRole('checkbox', { name: /Available now only/ }))
    await user.click(screen.getByRole('button', { name: 'Search' }))

    await screen.findByText('No nearby farms currently have this crop.')
    expect(api.searches).toEqual([
      {
        latitude: '35.2271',
        longitude: '-80.8431',
        radius_miles: '10',
        available_only: 'false',
        sort: 'price',
        query: 'strawberries',
        category: 'FRUITS',
      },
    ])
  })

  it.each([
    ['Latitude', '95', 'Latitude must be a number between -90 and 90.'],
    ['Longitude', 'west', 'Longitude must be a number between -180 and 180.'],
  ])('rejects %s "%s" without searching', async (fieldLabel, value, expectedMessage) => {
    const api = openDashboard()
    const user = userEvent.setup()

    await enterLocation(user)
    await user.clear(screen.getByLabelText(fieldLabel))
    await user.type(screen.getByLabelText(fieldLabel), value)
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(expectedMessage)
    expect(api.searches).toHaveLength(0)
  })
})

describe('search results', () => {
  it('shows each product with its farm, distance, price, stock and harvest date', async () => {
    openDashboard([
      buildSearchResult(),
      buildSearchResult({
        product: { id: 2, name: 'Free-Range Eggs', category: 'EGGS', unit: 'DOZEN', organic: false },
        farm: { id: 2, farm_name: 'Hilltop Hens', city: 'Concord', delivery_available: true },
        distance_miles: 12.84,
        price: '6',
        quantity_available: 0,
        harvest_date: null,
      }),
    ])
    const user = userEvent.setup()

    await enterLocation(user)
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByText('2 products within 25 miles')).toBeInTheDocument()

    const tomatoCard = within(screen.getByRole('heading', { name: 'Heirloom Tomatoes' }).closest('li')!)
    expect(tomatoCard.getByText('$4.50')).toBeInTheDocument()
    expect(tomatoCard.getByText('/ lb')).toBeInTheDocument()
    expect(tomatoCard.getByText('Organic')).toBeInTheDocument()
    expect(tomatoCard.getByText('Green Acres')).toBeInTheDocument()
    expect(tomatoCard.getByText('Charlotte, NC')).toBeInTheDocument()
    expect(tomatoCard.getByText('3.2 mi')).toBeInTheDocument()
    expect(tomatoCard.getByText('Pickup')).toBeInTheDocument()
    expect(tomatoCard.getByText('20 lb')).toBeInTheDocument()
    expect(tomatoCard.getByText('Jun 1, 2026')).toBeInTheDocument()

    const eggCard = within(screen.getByRole('heading', { name: 'Free-Range Eggs' }).closest('li')!)
    expect(eggCard.getByText('$6.00')).toBeInTheDocument()
    expect(eggCard.getByText('Hilltop Hens')).toBeInTheDocument()
    expect(eggCard.getByText('12.8 mi')).toBeInTheDocument()
    expect(eggCard.getByText('Pickup or delivery')).toBeInTheDocument()
    expect(eggCard.getByText('Out of stock')).toBeInTheDocument()
    expect(eggCard.getByText('Not stated')).toBeInTheDocument()
    expect(eggCard.queryByText('Organic')).not.toBeInTheDocument()
  })

  it('uses the singular for one result', async () => {
    openDashboard([buildSearchResult()])
    const user = userEvent.setup()

    await enterLocation(user)
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByText('1 product within 25 miles')).toBeInTheDocument()
  })

  it('tells the customer when no nearby farm has the crop they searched for', async () => {
    openDashboard([])
    const user = userEvent.setup()

    await enterLocation(user)
    await user.type(screen.getByLabelText('Search term'), 'okra')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(
      await screen.findByText('No nearby farms currently have this crop.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Try a wider radius/)).toBeInTheDocument()
  })

  it('shows an error when the search fails and recovers on the next search', async () => {
    const api = openDashboard([buildSearchResult()])
    api.failNextRequest('GET', '/api/products/search', 500, 'Internal Server Error')
    const user = userEvent.setup()

    await enterLocation(user)
    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The search could not be completed.')

    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByRole('heading', { name: 'Heirloom Tomatoes' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('using the current location', () => {
  function stubGeolocation(getCurrentPosition: Geolocation['getCurrentPosition']) {
    Object.defineProperty(window.navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition },
    })
  }

  afterEach(() => {
    Reflect.deleteProperty(window.navigator, 'geolocation')
  })

  it('fills in rounded coordinates from the browser', async () => {
    stubGeolocation((onSuccess) =>
      onSuccess({ coords: { latitude: 35.22712345, longitude: -80.84309876 } } as GeolocationPosition),
    )
    openDashboard()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Use my current location' }))

    expect(screen.getByLabelText('Latitude')).toHaveValue('35.227')
    expect(screen.getByLabelText('Longitude')).toHaveValue('-80.843')
  })

  it('asks for coordinates when the browser cannot provide a location', async () => {
    stubGeolocation((_onSuccess, onError) => onError?.({} as GeolocationPositionError))
    openDashboard()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Use my current location' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your location could not be determined. Enter your coordinates instead.',
    )
  })
})
