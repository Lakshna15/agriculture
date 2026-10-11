import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { EventSearchResult } from '../../api/events.ts'
import { buildEventSearchResult, buildUser, installFakeApi } from '../../test/fakeApi.ts'
import { renderApp } from '../../test/renderApp.tsx'

const customer = buildUser({ id: 1, name: 'Ana Grower', email: 'ana@example.com', role: 'CUSTOMER' })

function openExperiences(eventSearchResults: EventSearchResult[] = []) {
  const api = installFakeApi({
    accounts: [{ user: customer, password: 'correct-horse-battery' }],
    eventSearchResults,
  })
  api.signIn(customer)
  renderApp('/customer/experiences')
  return api
}

async function search(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Latitude'), '35.2271')
  await user.type(screen.getByLabelText('Longitude'), '-80.8431')
  await user.click(screen.getByRole('button', { name: 'Search' }))
}

async function findEventCard(title: string) {
  return within((await screen.findByRole('heading', { name: title })).closest('li')!)
}

describe('finding farm experiences', () => {
  it('searches with the location, radius and type that were chosen', async () => {
    const api = openExperiences()
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Latitude'), '35.2271')
    await user.type(screen.getByLabelText('Longitude'), '-80.8431')
    await user.selectOptions(screen.getByLabelText('Radius'), '50 miles')
    await user.selectOptions(screen.getByLabelText('Type of experience'), 'Farm tour')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    await screen.findByText('No upcoming farm experiences within 50 miles.')
    expect(api.eventSearches).toEqual([
      { latitude: '35.2271', longitude: '-80.8431', radius_miles: '50', event_type: 'FARM_TOUR' },
    ])
  })

  it('shows each experience with its time, price, farm, distance and places left', async () => {
    openExperiences([
      buildEventSearchResult({ event: { capacity: 20, spots_remaining: 14 } }),
      buildEventSearchResult({
        event: {
          id: 2,
          title: 'Sunset Farm Tour',
          event_type: 'FARM_TOUR',
          price: '0.00',
          start_time: '17:30:00',
          end_time: '19:00:00',
          capacity: 8,
          spots_remaining: 0,
        },
        farm: { id: 2, farm_name: 'Hilltop Hens', city: 'Concord' },
        distance_miles: 12.84,
      }),
    ])
    const user = userEvent.setup()
    await search(user)

    const berryCard = await findEventCard('Strawberry Picking Morning')
    expect(berryCard.getByText('Strawberry picking')).toBeInTheDocument()
    expect(berryCard.getByText('Jun 8, 2026')).toBeInTheDocument()
    expect(berryCard.getByText('9:00 AM to 12:00 PM')).toBeInTheDocument()
    expect(berryCard.getByText('$12.00')).toBeInTheDocument()
    expect(berryCard.getByText('Green Acres')).toBeInTheDocument()
    expect(berryCard.getByText('3.2 mi')).toBeInTheDocument()
    expect(berryCard.getByText('14 of 20 left')).toBeInTheDocument()

    const tourCard = await findEventCard('Sunset Farm Tour')
    expect(tourCard.getByText('Free')).toBeInTheDocument()
    expect(tourCard.getByText('5:30 PM to 7:00 PM')).toBeInTheDocument()
    expect(tourCard.getByText('12.8 mi')).toBeInTheDocument()
    expect(tourCard.getByText('Fully booked')).toBeInTheDocument()
    expect(tourCard.queryByRole('button', { name: /Reserve/ })).not.toBeInTheDocument()
  })

  it('rejects an invalid latitude without searching', async () => {
    const api = openExperiences()
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Latitude'), '120')
    await user.type(screen.getByLabelText('Longitude'), '-80.8431')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Latitude must be a number between -90 and 90.',
    )
    expect(api.eventSearches).toHaveLength(0)
  })
})

describe('reserving a farm experience', () => {
  it('reserves places for the party and shows how many are left', async () => {
    const api = openExperiences([
      buildEventSearchResult({ event: { capacity: 20, spots_remaining: 14 } }),
    ])
    const user = userEvent.setup()
    await search(user)
    const card = await findEventCard('Strawberry Picking Morning')

    await user.click(card.getByRole('button', { name: 'Reserve Strawberry Picking Morning' }))
    await user.clear(card.getByLabelText('Party size'))
    await user.type(card.getByLabelText('Party size'), '4')
    await user.click(card.getByRole('button', { name: 'Confirm reservation' }))

    expect(await card.findByRole('status')).toHaveTextContent('Reserved for a party of 4.')
    expect(card.getByText('10 of 20 left')).toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/event-reservations')).toEqual([
      { method: 'POST', path: '/api/event-reservations', body: { event_id: 1, party_size: 4 } },
    ])
  })

  it.each(['0', '15', '2.5'])(
    'rejects the party size "%s" without calling the API',
    async (partySize) => {
      const api = openExperiences([
        buildEventSearchResult({ event: { capacity: 20, spots_remaining: 14 } }),
      ])
      const user = userEvent.setup()
      await search(user)
      const card = await findEventCard('Strawberry Picking Morning')

      await user.click(card.getByRole('button', { name: 'Reserve Strawberry Picking Morning' }))
      await user.clear(card.getByLabelText('Party size'))
      await user.type(card.getByLabelText('Party size'), partySize)
      await user.click(card.getByRole('button', { name: 'Confirm reservation' }))

      expect(await card.findByRole('alert')).toHaveTextContent(
        'Party size must be a whole number between 1 and 14.',
      )
      expect(api.requestsTo('POST', '/api/event-reservations')).toHaveLength(0)
    },
  )

  it('shows the server message when the event fills up in the meantime', async () => {
    const api = openExperiences([
      buildEventSearchResult({ event: { capacity: 20, spots_remaining: 14 } }),
    ])
    api.failNextRequest('POST', '/api/event-reservations', 409, 'Only 1 spots remaining')
    const user = userEvent.setup()
    await search(user)
    const card = await findEventCard('Strawberry Picking Morning')

    await user.click(card.getByRole('button', { name: 'Reserve Strawberry Picking Morning' }))
    await user.click(card.getByRole('button', { name: 'Confirm reservation' }))

    expect(await card.findByRole('alert')).toHaveTextContent('Only 1 spots remaining')
    expect(card.getByText('14 of 20 left')).toBeInTheDocument()
  })
})

describe('moving between the customer pages', () => {
  it('keeps the search location when switching from products to experiences', async () => {
    const api = installFakeApi({ accounts: [{ user: customer, password: 'correct-horse-battery' }] })
    api.signIn(customer)
    renderApp('/customer')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Latitude'), '35.2271')
    await user.type(screen.getByLabelText('Longitude'), '-80.8431')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await screen.findByText('No products were found within 25 miles.')

    const tabs = within(screen.getByRole('navigation', { name: 'Customer dashboard sections' }))
    await user.click(tabs.getByRole('link', { name: 'Farm experiences' }))

    expect(await screen.findByRole('heading', { name: 'Find farm experiences' })).toBeInTheDocument()
    expect(screen.getByLabelText('Latitude')).toHaveValue('35.2271')
    expect(screen.getByLabelText('Longitude')).toHaveValue('-80.8431')
  })
})
