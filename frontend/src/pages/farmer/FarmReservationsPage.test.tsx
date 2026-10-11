import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { EventReservation } from '../../api/events.ts'
import type { ProductReservation } from '../../api/reservations.ts'
import {
  buildEventReservation,
  buildFarm,
  buildProductReservation,
  buildUser,
  installFakeApi,
} from '../../test/fakeApi.ts'
import { renderApp } from '../../test/renderApp.tsx'

const farmer = buildUser({ id: 7, name: 'Ben Fields', email: 'ben@example.com', role: 'FARMER' })
const farm = buildFarm({ id: 3, owner_id: farmer.id })

function openReservations(data: {
  productReservations?: ProductReservation[]
  eventReservations?: EventReservation[]
}) {
  const api = installFakeApi({
    accounts: [{ user: farmer, password: 'tractor-barn-orchard' }],
    farms: [farm],
    ...data,
  })
  api.signIn(farmer)
  renderApp('/farmer/reservations')
  return api
}

async function findSection(name: string) {
  return within(await screen.findByRole('region', { name }))
}

function buttonLabels(section: {
  queryAllByRole: (role: 'button') => HTMLElement[]
}): (string | null)[] {
  return section.queryAllByRole('button').map((button) => button.textContent)
}

describe('farm reservations', () => {
  it('says so when no customer has reserved anything', async () => {
    openReservations({})

    const products = await findSection('Product reservations')
    const events = await findSection('Event reservations')

    expect(await products.findByText(/No one has reserved your products yet/)).toBeInTheDocument()
    expect(
      await events.findByText(/No one has reserved a place at your events yet/),
    ).toBeInTheDocument()
  })

  it('shows who reserved what, and when they will collect it', async () => {
    openReservations({
      productReservations: [buildProductReservation()],
      eventReservations: [buildEventReservation()],
    })

    const products = await findSection('Product reservations')
    expect(await products.findByRole('heading', { name: 'Heirloom Tomatoes' })).toBeInTheDocument()
    expect(products.getByText('Reserved by Ana Grower')).toBeInTheDocument()
    expect(products.getByText('3 lb · Pickup Jun 1, 2026 at 10:30 AM')).toBeInTheDocument()

    const events = await findSection('Event reservations')
    expect(
      await events.findByRole('heading', { name: 'Strawberry Picking Morning' }),
    ).toBeInTheDocument()
    expect(events.getByText('Reserved by Ana Grower · party of 4')).toBeInTheDocument()
    expect(events.getByText('Jun 8, 2026, 9:00 AM to 12:00 PM')).toBeInTheDocument()
  })

  it('confirms a pending product reservation and then completes it', async () => {
    const api = openReservations({ productReservations: [buildProductReservation({ id: 5 })] })
    const user = userEvent.setup()
    const products = await findSection('Product reservations')

    await products.findByRole('heading', { name: 'Heirloom Tomatoes' })
    expect(buttonLabels(products)).toEqual(['Confirm', 'Cancel'])

    await user.click(
      products.getByRole('button', { name: 'Confirm reservation for Heirloom Tomatoes' }),
    )
    expect(await products.findByText('Confirmed')).toBeInTheDocument()
    expect(buttonLabels(products)).toEqual(['Mark completed', 'Cancel'])

    await user.click(
      products.getByRole('button', { name: 'Mark completed reservation for Heirloom Tomatoes' }),
    )
    expect(await products.findByText('Completed')).toBeInTheDocument()
    expect(buttonLabels(products)).toEqual([])

    expect(
      api.requestsTo('PATCH', '/api/reservations/5/status').map((request) => request.body),
    ).toEqual([{ status: 'CONFIRMED' }, { status: 'COMPLETED' }])
  })

  it('cancels a product reservation', async () => {
    const api = openReservations({ productReservations: [buildProductReservation({ id: 5 })] })
    const user = userEvent.setup()
    const products = await findSection('Product reservations')

    await user.click(
      await products.findByRole('button', { name: 'Cancel reservation for Heirloom Tomatoes' }),
    )

    expect(await products.findByText('Cancelled')).toBeInTheDocument()
    expect(buttonLabels(products)).toEqual([])
    expect(api.requestsTo('PATCH', '/api/reservations/5/status')[0].body).toEqual({
      status: 'CANCELLED',
    })
  })

  it('confirms an event reservation', async () => {
    const api = openReservations({ eventReservations: [buildEventReservation({ id: 8 })] })
    const user = userEvent.setup()
    const events = await findSection('Event reservations')

    await user.click(
      await events.findByRole('button', {
        name: 'Confirm reservation for Strawberry Picking Morning',
      }),
    )

    expect(await events.findByText('Confirmed')).toBeInTheDocument()
    expect(api.requestsTo('PATCH', '/api/event-reservations/8/status')[0].body).toEqual({
      status: 'CONFIRMED',
    })
  })

  it('shows the server message when a status change is refused', async () => {
    const api = openReservations({ productReservations: [buildProductReservation({ id: 5 })] })
    api.failNextRequest(
      'PATCH',
      '/api/reservations/5/status',
      409,
      'A CANCELLED reservation cannot be changed to CONFIRMED',
    )
    const user = userEvent.setup()
    const products = await findSection('Product reservations')

    await user.click(
      await products.findByRole('button', { name: 'Confirm reservation for Heirloom Tomatoes' }),
    )

    expect(await products.findByRole('alert')).toHaveTextContent(
      'A CANCELLED reservation cannot be changed to CONFIRMED',
    )
    expect(products.getByText('Pending')).toBeInTheDocument()
  })
})

describe('farmer dashboard tabs', () => {
  it('moves between the farm, events and reservations pages', async () => {
    openReservations({})
    const user = userEvent.setup()
    const tabs = within(
      await screen.findByRole('navigation', { name: 'Farmer dashboard sections' }),
    )

    await user.click(tabs.getByRole('link', { name: 'Farm events' }))
    expect(await screen.findByRole('heading', { name: 'Farm events' })).toBeInTheDocument()

    await user.click(tabs.getByRole('link', { name: 'Farm and products' }))
    expect(await screen.findByRole('heading', { name: 'Green Acres' })).toBeInTheDocument()

    await user.click(tabs.getByRole('link', { name: 'Reservations' }))
    expect(await screen.findByRole('region', { name: 'Product reservations' })).toBeInTheDocument()
  })
})
