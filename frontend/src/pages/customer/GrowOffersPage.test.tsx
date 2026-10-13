import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { CropCommitment, GrowOfferSearchResult } from '../../api/growOffers.ts'
import {
  buildCropCommitment,
  buildGrowOfferSearchResult,
  buildUser,
  installFakeApi,
} from '../../test/fakeApi.ts'
import { renderApp } from '../../test/renderApp.tsx'

const customer = buildUser({ id: 1, name: 'Ana Grower', email: 'ana@example.com', role: 'CUSTOMER' })

function openGrowOffers(data: {
  growOfferSearchResults?: GrowOfferSearchResult[]
  commitments?: CropCommitment[]
}) {
  const api = installFakeApi({
    accounts: [{ user: customer, password: 'correct-horse-battery' }],
    ...data,
  })
  api.signIn(customer)
  renderApp('/customer/grow-offers')
  return api
}

async function search(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Latitude'), '35.227')
  await user.type(screen.getByLabelText('Longitude'), '-80.843')
  await user.click(screen.getByRole('button', { name: 'Search' }))
}

async function findOfferCard(cropName: string) {
  const results = within(await screen.findByRole('region', { name: 'Grow offers found' }))
  return within((await results.findByRole('heading', { name: cropName })).closest('li')!)
}

async function findCommitments() {
  return within(await screen.findByRole('region', { name: 'My commitments' }))
}

describe('browsing grow offers', () => {
  it('searches with the location, radius and crop that were entered', async () => {
    const api = openGrowOffers({})
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Latitude'), '35.227')
    await user.type(screen.getByLabelText('Longitude'), '-80.843')
    await user.selectOptions(screen.getByLabelText('Radius'), '50 miles')
    await user.type(screen.getByLabelText('Crop'), ' okra ')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    await screen.findByText('No grow offers within 50 miles yet.')
    expect(api.growOfferSearches).toEqual([
      { latitude: '35.227', longitude: '-80.843', radius_miles: '50', crop: 'okra' },
    ])
  })

  it('shows an offer with its farm, price, dates and commitment progress', async () => {
    openGrowOffers({ growOfferSearchResults: [buildGrowOfferSearchResult()] })
    const user = userEvent.setup()
    await search(user)

    const card = await findOfferCard('Okra')

    expect(card.getByText('Open')).toBeInTheDocument()
    expect(card.getByText('Green Acres · Charlotte, NC · 3.2 mi')).toBeInTheDocument()
    expect(card.getByText('$3.50')).toBeInTheDocument()
    expect(card.getByText('12 / 20 customers committed')).toBeInTheDocument()
    expect(card.getByText('40 of 100 lb spoken for')).toBeInTheDocument()
    expect(card.getByText('Apr 15, 2026')).toBeInTheDocument()
    expect(card.getByText('Jul 1, 2026')).toBeInTheDocument()
    const progress = card.getByRole('progressbar', { name: 'Commitment progress for Okra' })
    expect(progress).toHaveAttribute('aria-valuenow', '12')
    expect(progress).toHaveAttribute('aria-valuemax', '20')
  })

  it('points to crop requests when no offers are nearby', async () => {
    openGrowOffers({})
    const user = userEvent.setup()
    await search(user)

    expect(await screen.findByText('No grow offers within 25 miles yet.')).toBeInTheDocument()
    expect(screen.getByText(/Request the crop you want under Crop requests/)).toBeInTheDocument()
  })
})

describe('joining a grow offer', () => {
  it('commits to a quantity and shows the new progress', async () => {
    const api = openGrowOffers({ growOfferSearchResults: [buildGrowOfferSearchResult()] })
    const user = userEvent.setup()
    await search(user)
    const card = await findOfferCard('Okra')

    await user.click(card.getByRole('button', { name: 'Join grow offer for Okra' }))
    await user.clear(card.getByLabelText('Quantity (lb)'))
    await user.type(card.getByLabelText('Quantity (lb)'), '5')
    await user.click(card.getByRole('button', { name: 'Commit' }))

    expect(await card.findByRole('status')).toHaveTextContent(
      'You committed to 5 lb of this crop.',
    )
    expect(card.getByText('13 / 20 customers committed')).toBeInTheDocument()
    expect(card.getByText('45 of 100 lb spoken for')).toBeInTheDocument()
    expect(card.queryByRole('button', { name: /Join grow offer/ })).not.toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/crop-commitments')).toEqual([
      { method: 'POST', path: '/api/crop-commitments', body: { grow_offer_id: 1, quantity: 5 } },
    ])

    const commitments = await findCommitments()
    expect(commitments.getByRole('heading', { name: 'Okra' })).toBeInTheDocument()
    expect(commitments.getByText('You committed to 5 lb at about $3.50 / lb')).toBeInTheDocument()
  })

  it('shows the offer as confirmed when the commitment reaches the minimum', async () => {
    openGrowOffers({
      growOfferSearchResults: [
        buildGrowOfferSearchResult({ offer: { committed_customers: 19, minimum_customers: 20 } }),
      ],
    })
    const user = userEvent.setup()
    await search(user)
    const card = await findOfferCard('Okra')
    expect(card.getByText('Open')).toBeInTheDocument()

    await user.click(card.getByRole('button', { name: 'Join grow offer for Okra' }))
    await user.click(card.getByRole('button', { name: 'Commit' }))

    expect(await card.findByText('Confirmed')).toBeInTheDocument()
    expect(card.getByText('20 / 20 customers committed')).toBeInTheDocument()
  })

  it('shows an offer the customer already joined without a join button', async () => {
    openGrowOffers({
      growOfferSearchResults: [buildGrowOfferSearchResult()],
      commitments: [buildCropCommitment({ quantity: 8 })],
    })
    const user = userEvent.setup()
    await search(user)

    const card = await findOfferCard('Okra')

    expect(await card.findByText('You committed to 8 lb of this crop.')).toBeInTheDocument()
    expect(card.queryByRole('button', { name: /Join grow offer/ })).not.toBeInTheDocument()
  })

  it('offers no join button when the whole harvest is spoken for', async () => {
    openGrowOffers({
      growOfferSearchResults: [
        buildGrowOfferSearchResult({ offer: { expected_quantity: 100, committed_quantity: 100 } }),
      ],
    })
    const user = userEvent.setup()
    await search(user)

    const card = await findOfferCard('Okra')

    expect(card.getByText('The whole expected harvest is spoken for.')).toBeInTheDocument()
    expect(card.queryByRole('button', { name: /Join grow offer/ })).not.toBeInTheDocument()
  })

  it.each(['0', '61', '1.5'])(
    'rejects the quantity "%s" without calling the API',
    async (quantity) => {
      const api = openGrowOffers({ growOfferSearchResults: [buildGrowOfferSearchResult()] })
      const user = userEvent.setup()
      await search(user)
      const card = await findOfferCard('Okra')

      await user.click(card.getByRole('button', { name: 'Join grow offer for Okra' }))
      await user.clear(card.getByLabelText('Quantity (lb)'))
      await user.type(card.getByLabelText('Quantity (lb)'), quantity)
      await user.click(card.getByRole('button', { name: 'Commit' }))

      expect(await card.findByRole('alert')).toHaveTextContent(
        'Quantity must be a whole number between 1 and 60.',
      )
      expect(api.requestsTo('POST', '/api/crop-commitments')).toHaveLength(0)
    },
  )

  it('shows the server message when the offer has closed in the meantime', async () => {
    const api = openGrowOffers({ growOfferSearchResults: [buildGrowOfferSearchResult()] })
    api.failNextRequest(
      'POST',
      '/api/crop-commitments',
      409,
      'This grow offer is no longer accepting commitments',
    )
    const user = userEvent.setup()
    await search(user)
    const card = await findOfferCard('Okra')

    await user.click(card.getByRole('button', { name: 'Join grow offer for Okra' }))
    await user.click(card.getByRole('button', { name: 'Commit' }))

    expect(await card.findByRole('alert')).toHaveTextContent(
      'This grow offer is no longer accepting commitments',
    )
    expect(card.getByText('12 / 20 customers committed')).toBeInTheDocument()
  })
})

describe('my commitments', () => {
  it('says so when the customer has not joined any offer', async () => {
    openGrowOffers({})

    const commitments = await findCommitments()

    expect(
      await commitments.findByText('You have not joined any grow offers yet.'),
    ).toBeInTheDocument()
  })

  it('shows each commitment with the offer status and progress', async () => {
    openGrowOffers({
      commitments: [
        buildCropCommitment({
          quantity: 8,
          offer: { status: 'CONFIRMED', committed_customers: 22, committed_quantity: 70 },
        }),
      ],
    })

    const commitments = await findCommitments()

    expect(await commitments.findByRole('heading', { name: 'Okra' })).toBeInTheDocument()
    expect(commitments.getByText('Confirmed')).toBeInTheDocument()
    expect(commitments.getByText('You committed to 8 lb at about $3.50 / lb')).toBeInTheDocument()
    expect(
      commitments.getByText('Green Acres, Charlotte, NC · Expected harvest Jul 1, 2026'),
    ).toBeInTheDocument()
    expect(commitments.getByText('22 / 20 customers committed')).toBeInTheDocument()
    // The bar is full once the minimum is met, even when more customers have joined.
    expect(commitments.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '20')
  })
})
