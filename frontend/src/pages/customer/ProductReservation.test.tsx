import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { ProductSearchResult } from '../../api/products.ts'
import { todayAsIsoDate } from '../../lib/format.ts'
import { buildSearchResult, buildUser, installFakeApi } from '../../test/fakeApi.ts'
import { renderApp } from '../../test/renderApp.tsx'

const customer = buildUser({ id: 1, name: 'Ana Grower', email: 'ana@example.com', role: 'CUSTOMER' })

/** Signs in a customer, opens the dashboard and runs a search that returns the given results. */
async function searchFor(searchResults: ProductSearchResult[]) {
  const api = installFakeApi({
    accounts: [{ user: customer, password: 'correct-horse-battery' }],
    searchResults,
  })
  api.signIn(customer)
  renderApp('/customer')
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('Latitude'), '35.2271')
  await user.type(screen.getByLabelText('Longitude'), '-80.8431')
  await user.click(screen.getByRole('button', { name: 'Search' }))
  const card = within((await screen.findByRole('heading', { name: 'Heirloom Tomatoes' })).closest('li')!)
  return { api, user, card }
}

describe('reserving a product from the search results', () => {
  it('reserves the chosen quantity and shows the reduced stock', async () => {
    const { api, user, card } = await searchFor([buildSearchResult({ quantity_available: 20 })])

    await user.click(card.getByRole('button', { name: 'Reserve Heirloom Tomatoes' }))
    await user.clear(card.getByLabelText('Quantity (lb)'))
    await user.type(card.getByLabelText('Quantity (lb)'), '3')
    await user.clear(card.getByLabelText('Pickup time'))
    await user.type(card.getByLabelText('Pickup time'), '14:30')
    await user.click(card.getByRole('button', { name: 'Confirm reservation' }))

    expect(await card.findByRole('status')).toHaveTextContent(/Reserved 3 lb for pickup on .* at 2:30 PM/)
    expect(card.getByText('17 lb')).toBeInTheDocument()
    expect(card.getByRole('link', { name: 'View my reservations' })).toHaveAttribute(
      'href',
      '/customer/reservations',
    )
    expect(api.requestsTo('POST', '/api/reservations')).toEqual([
      {
        method: 'POST',
        path: '/api/reservations',
        body: { product_id: 1, quantity: 3, pickup_date: todayAsIsoDate(), pickup_time: '14:30' },
      },
    ])
  })

  it('offers no reserve button for a product that is out of stock', async () => {
    const { card } = await searchFor([buildSearchResult({ quantity_available: 0 })])

    expect(card.getByText('Out of stock')).toBeInTheDocument()
    expect(card.queryByRole('button', { name: /Reserve/ })).not.toBeInTheDocument()
  })

  it.each(['0', '21', '1.5', 'some'])(
    'rejects the quantity "%s" without calling the API',
    async (quantity) => {
      const { api, user, card } = await searchFor([buildSearchResult({ quantity_available: 20 })])

      await user.click(card.getByRole('button', { name: 'Reserve Heirloom Tomatoes' }))
      await user.clear(card.getByLabelText('Quantity (lb)'))
      await user.type(card.getByLabelText('Quantity (lb)'), quantity)
      await user.click(card.getByRole('button', { name: 'Confirm reservation' }))

      expect(await card.findByRole('alert')).toHaveTextContent(
        'Quantity must be a whole number between 1 and 20.',
      )
      expect(api.requestsTo('POST', '/api/reservations')).toHaveLength(0)
    },
  )

  it('shows the server message when the stock has gone in the meantime', async () => {
    const { api, user, card } = await searchFor([buildSearchResult({ quantity_available: 20 })])
    api.failNextRequest('POST', '/api/reservations', 409, 'Only 2 available')

    await user.click(card.getByRole('button', { name: 'Reserve Heirloom Tomatoes' }))
    await user.click(card.getByRole('button', { name: 'Confirm reservation' }))

    expect(await card.findByRole('alert')).toHaveTextContent('Only 2 available')
    expect(card.getByText('20 lb')).toBeInTheDocument()
    expect(card.getByRole('button', { name: 'Confirm reservation' })).toBeEnabled()
  })

  it('closes the form without reserving when cancelled', async () => {
    const { api, user, card } = await searchFor([buildSearchResult({ quantity_available: 20 })])

    await user.click(card.getByRole('button', { name: 'Reserve Heirloom Tomatoes' }))
    await user.click(card.getByRole('button', { name: 'Cancel' }))

    expect(card.queryByLabelText('Quantity (lb)')).not.toBeInTheDocument()
    expect(card.getByRole('button', { name: 'Reserve Heirloom Tomatoes' })).toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/reservations')).toHaveLength(0)
  })
})
