import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { EventReservation } from '../../api/events.ts'
import type { ProductReservation } from '../../api/reservations.ts'
import {
  buildEventReservation,
  buildProductReservation,
  buildUser,
  installFakeApi,
} from '../../test/fakeApi.ts'
import { renderApp } from '../../test/renderApp.tsx'

const customer = buildUser({ id: 1, name: 'Ana Grower', email: 'ana@example.com', role: 'CUSTOMER' })

function openReservations(data: {
  productReservations?: ProductReservation[]
  eventReservations?: EventReservation[]
}) {
  const api = installFakeApi({
    accounts: [{ user: customer, password: 'correct-horse-battery' }],
    ...data,
  })
  api.signIn(customer)
  renderApp('/customer/reservations')
  return api
}

async function findSection(name: string) {
  return within(await screen.findByRole('region', { name }))
}

describe('customer reservations', () => {
  it('explains where to start when nothing has been reserved', async () => {
    openReservations({})

    const products = await findSection('Product reservations')
    const experiences = await findSection('Farm experience reservations')

    expect(await products.findByText(/You have not reserved any products yet/)).toBeInTheDocument()
    expect(
      await experiences.findByText(/You have not reserved any farm experiences yet/),
    ).toBeInTheDocument()
  })

  it('shows a product reservation with its pickup details and farm address', async () => {
    openReservations({ productReservations: [buildProductReservation()] })

    const products = await findSection('Product reservations')

    expect(await products.findByRole('heading', { name: 'Heirloom Tomatoes' })).toBeInTheDocument()
    expect(products.getByText('Pending')).toBeInTheDocument()
    expect(products.getByText('3 lb · Pickup Jun 1, 2026 at 10:30 AM')).toBeInTheDocument()
    expect(
      products.getByText('Green Acres, 100 Orchard Road, Charlotte, NC 28202'),
    ).toBeInTheDocument()
    expect(products.getByText('Farm phone: 704-555-0100')).toBeInTheDocument()
  })

  it('shows a farm experience reservation with its date, price and party size', async () => {
    openReservations({ eventReservations: [buildEventReservation({ status: 'CONFIRMED' })] })

    const experiences = await findSection('Farm experience reservations')

    expect(
      await experiences.findByRole('heading', { name: 'Strawberry Picking Morning' }),
    ).toBeInTheDocument()
    expect(experiences.getByText('Confirmed')).toBeInTheDocument()
    expect(
      experiences.getByText('Party of 4 · Jun 8, 2026, 9:00 AM to 12:00 PM'),
    ).toBeInTheDocument()
    expect(experiences.getByText('$12.00 per person')).toBeInTheDocument()
  })

  it('cancels a product reservation', async () => {
    const api = openReservations({ productReservations: [buildProductReservation({ id: 7 })] })
    const user = userEvent.setup()
    const products = await findSection('Product reservations')

    await user.click(
      await products.findByRole('button', { name: 'Cancel reservation for Heirloom Tomatoes' }),
    )

    expect(await products.findByText('Cancelled')).toBeInTheDocument()
    expect(products.queryByRole('button', { name: /Cancel reservation/ })).not.toBeInTheDocument()
    expect(api.requestsTo('PATCH', '/api/reservations/7/status')).toEqual([
      { method: 'PATCH', path: '/api/reservations/7/status', body: { status: 'CANCELLED' } },
    ])
  })

  it('cancels a farm experience reservation', async () => {
    const api = openReservations({ eventReservations: [buildEventReservation({ id: 9 })] })
    const user = userEvent.setup()
    const experiences = await findSection('Farm experience reservations')

    await user.click(
      await experiences.findByRole('button', {
        name: 'Cancel reservation for Strawberry Picking Morning',
      }),
    )

    expect(await experiences.findByText('Cancelled')).toBeInTheDocument()
    expect(api.requestsTo('PATCH', '/api/event-reservations/9/status')[0].body).toEqual({
      status: 'CANCELLED',
    })
  })

  it('offers the customer only cancellation, and nothing once a reservation is final', async () => {
    openReservations({
      productReservations: [
        buildProductReservation({ id: 1, status: 'CONFIRMED' }),
        buildProductReservation({
          id: 2,
          status: 'COMPLETED',
          product: { id: 2, name: 'Free-Range Eggs', unit: 'DOZEN' },
        }),
      ],
    })
    const products = await findSection('Product reservations')

    const confirmedCard = within(
      (await products.findByRole('heading', { name: 'Heirloom Tomatoes' })).closest('li')!,
    )
    const completedCard = within(
      products.getByRole('heading', { name: 'Free-Range Eggs' }).closest('li')!,
    )

    expect(confirmedCard.getAllByRole('button').map((button) => button.textContent)).toEqual([
      'Cancel',
    ])
    expect(completedCard.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows the server message when a cancellation is refused', async () => {
    const api = openReservations({ productReservations: [buildProductReservation({ id: 7 })] })
    api.failNextRequest(
      'PATCH',
      '/api/reservations/7/status',
      409,
      'A COMPLETED reservation cannot be changed to CANCELLED',
    )
    const user = userEvent.setup()
    const products = await findSection('Product reservations')

    await user.click(
      await products.findByRole('button', { name: 'Cancel reservation for Heirloom Tomatoes' }),
    )

    expect(await products.findByRole('alert')).toHaveTextContent(
      'A COMPLETED reservation cannot be changed to CANCELLED',
    )
    expect(products.getByText('Pending')).toBeInTheDocument()
  })

  it('shows an error with a retry when reservations cannot be loaded', async () => {
    const api = openReservations({ productReservations: [buildProductReservation()] })
    api.failNextRequest('GET', '/api/reservations/mine', 500, 'Internal Server Error')
    const user = userEvent.setup()
    const products = await findSection('Product reservations')

    expect(await products.findByRole('alert')).toHaveTextContent(
      'These reservations could not be loaded.',
    )
    await user.click(products.getByRole('button', { name: 'Try again' }))

    expect(await products.findByRole('heading', { name: 'Heirloom Tomatoes' })).toBeInTheDocument()
  })
})
