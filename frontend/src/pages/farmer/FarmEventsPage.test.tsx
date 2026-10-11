import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { FarmEvent } from '../../api/events.ts'
import { buildFarm, buildFarmEvent, buildUser, installFakeApi } from '../../test/fakeApi.ts'
import { renderApp } from '../../test/renderApp.tsx'

const farmer = buildUser({ id: 7, name: 'Ben Fields', email: 'ben@example.com', role: 'FARMER' })
const farm = buildFarm({ id: 3, owner_id: farmer.id })

function openEvents(events: FarmEvent[] = [], farms = [farm]) {
  const api = installFakeApi({
    accounts: [{ user: farmer, password: 'tractor-barn-orchard' }],
    farms,
    events,
  })
  api.signIn(farmer)
  renderApp('/farmer/events')
  return api
}

async function fillEventForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Event title'), 'Pumpkin Patch Day')
  await user.selectOptions(screen.getByLabelText('Type of event'), 'Pumpkin picking')
  await user.type(screen.getByLabelText('Event date'), '2030-10-12')
  await user.type(screen.getByLabelText('Price per person'), '8.50')
  await user.type(screen.getByLabelText('Capacity'), '40')
}

describe('farm events', () => {
  it('explains what events are for when none exist', async () => {
    openEvents()

    expect(
      await screen.findByText('You have not created any farm events yet'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create Farm Event' })).toBeInTheDocument()
  })

  it('lists existing events with their time, price and places remaining', async () => {
    openEvents([
      buildFarmEvent({ capacity: 20, spots_remaining: 14 }),
      buildFarmEvent({
        id: 2,
        title: 'Sunset Farm Tour',
        event_type: 'FARM_TOUR',
        price: '0.00',
        start_time: '17:30:00',
        end_time: '19:00:00',
        capacity: 8,
        spots_remaining: 8,
      }),
    ])

    expect(
      await screen.findByRole('heading', { name: 'Strawberry Picking Morning' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Strawberry picking · Jun 8, 2026, 9:00 AM to 12:00 PM · $12.00 per person'),
    ).toBeInTheDocument()
    expect(screen.getByText('14 of 20 places remaining')).toBeInTheDocument()
    expect(
      screen.getByText('Farm tour · Jun 8, 2026, 5:30 PM to 7:00 PM · Free'),
    ).toBeInTheDocument()
    expect(screen.getByText('8 of 8 places remaining')).toBeInTheDocument()
  })

  it('creates an event and adds it to the list', async () => {
    const api = openEvents()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Create Farm Event' }))
    await fillEventForm(user)
    await user.click(screen.getByRole('button', { name: 'Create event' }))

    expect(await screen.findByText('Pumpkin Patch Day has been created.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Pumpkin Patch Day' })).toBeInTheDocument()
    expect(screen.getByText('40 of 40 places remaining')).toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/events')[0].body).toEqual({
      title: 'Pumpkin Patch Day',
      description: null,
      event_type: 'PUMPKIN_PICKING',
      event_date: '2030-10-12',
      start_time: '09:00',
      end_time: '12:00',
      price: '8.50',
      capacity: 40,
    })
  })

  it('rejects an event that ends before it starts without calling the API', async () => {
    const api = openEvents()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Create Farm Event' }))
    await fillEventForm(user)
    await user.clear(screen.getByLabelText('End time'))
    await user.type(screen.getByLabelText('End time'), '08:00')
    await user.click(screen.getByRole('button', { name: 'Create event' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The end time must be after the start time.',
    )
    expect(api.requestsTo('POST', '/api/events')).toHaveLength(0)
  })

  it.each([
    ['Price per person', 'ten', 'Price must be zero or more'],
    ['Capacity', '0', 'Capacity must be a whole number of at least 1.'],
  ])('rejects an invalid %s without calling the API', async (fieldLabel, value, message) => {
    const api = openEvents()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Create Farm Event' }))
    await fillEventForm(user)
    await user.clear(screen.getByLabelText(fieldLabel))
    await user.type(screen.getByLabelText(fieldLabel), value)
    await user.click(screen.getByRole('button', { name: 'Create event' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(api.requestsTo('POST', '/api/events')).toHaveLength(0)
  })

  it('tells a farmer without a farm to create one first', async () => {
    openEvents([], [])
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Create Farm Event' }))
    await fillEventForm(user)
    await user.click(screen.getByRole('button', { name: 'Create event' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Create your farm first')
  })
})
