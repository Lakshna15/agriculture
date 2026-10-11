import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Product } from '../../api/products.ts'
import { buildFarm, buildProduct, buildUser, installFakeApi } from '../../test/fakeApi.ts'
import { renderApp } from '../../test/renderApp.tsx'

const farmer = buildUser({ id: 7, name: 'Ben Fields', email: 'ben@example.com', role: 'FARMER' })
const farm = buildFarm({ id: 3, owner_id: farmer.id })
const tomatoes = buildProduct({ id: 11, farm_id: farm.id })

function openDashboard(products: Product[] = [tomatoes]) {
  const api = installFakeApi({
    accounts: [{ user: farmer, password: 'tractor-barn-orchard' }],
    farms: [farm],
    products,
  })
  api.signIn(farmer)
  renderApp('/farmer')
  return api
}

async function findProductsSection() {
  return within(await screen.findByRole('region', { name: 'Products' }))
}

describe('listing products', () => {
  it('explains what to do when the farm has no products', async () => {
    openDashboard([])
    const products = await findProductsSection()

    expect(await products.findByText('You have not listed any products yet')).toBeInTheDocument()
    expect(products.getByRole('button', { name: 'Add Product' })).toBeInTheDocument()
  })

  it('shows each product with its price, stock and status', async () => {
    openDashboard([
      tomatoes,
      buildProduct({
        id: 12,
        farm_id: farm.id,
        name: 'Free-Range Eggs',
        category: 'EGGS',
        price: '6.00',
        unit: 'DOZEN',
        quantity_available: 0,
        organic: false,
        active: false,
        harvest_date: '2026-06-01',
      }),
    ])
    const products = await findProductsSection()

    const tomatoHeading = await products.findByRole('heading', { name: 'Heirloom Tomatoes' })
    const tomatoItem = within(tomatoHeading.closest('li')!)
    expect(tomatoItem.getByText('Vegetables · $4.50 / lb')).toBeInTheDocument()
    expect(tomatoItem.getByText('20 lb in stock')).toBeInTheDocument()
    expect(tomatoItem.getByText('Organic')).toBeInTheDocument()
    expect(tomatoItem.queryByText('Hidden from customers')).not.toBeInTheDocument()

    const eggItem = within(
      products.getByRole('heading', { name: 'Free-Range Eggs' }).closest('li')!,
    )
    expect(eggItem.getByText('Eggs · $6.00 / dozen · Harvested Jun 1, 2026')).toBeInTheDocument()
    expect(eggItem.getByText('0 dozen in stock')).toBeInTheDocument()
    expect(eggItem.getByText('Hidden from customers')).toBeInTheDocument()
  })
})

describe('adding a product', () => {
  it('sends the new product and adds it to the list', async () => {
    const api = openDashboard([])
    const user = userEvent.setup()
    const products = await findProductsSection()

    await user.click(await products.findByRole('button', { name: 'Add Product' }))
    await user.type(products.getByLabelText('Product name'), 'Strawberries')
    await user.selectOptions(products.getByLabelText('Category'), 'Fruits')
    await user.type(products.getByLabelText('Price'), '5.25')
    await user.selectOptions(products.getByLabelText('Sold by'), 'pint')
    await user.clear(products.getByLabelText('Quantity available'))
    await user.type(products.getByLabelText('Quantity available'), '30')
    await user.type(products.getByLabelText('Harvest date'), '2026-06-01')
    await user.click(products.getByRole('button', { name: 'Add Product' }))

    expect(await products.findByText('Strawberries has been added.')).toBeInTheDocument()
    expect(products.getByText('Fruits · $5.25 / pint · Harvested Jun 1, 2026')).toBeInTheDocument()
    expect(products.getByText('30 pint in stock')).toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/products')[0].body).toEqual({
      name: 'Strawberries',
      category: 'FRUITS',
      description: null,
      price: '5.25',
      unit: 'PINT',
      quantity_available: 30,
      harvest_date: '2026-06-01',
      available_from: null,
      available_until: null,
      organic: false,
      active: true,
    })
  })

  it.each([
    ['4.999', 'Price must be more than zero'],
    ['0', 'Price must be more than zero'],
    ['cheap', 'Price must be more than zero'],
  ])('rejects the price "%s" without calling the API', async (price, expectedMessage) => {
    const api = openDashboard([])
    const user = userEvent.setup()
    const products = await findProductsSection()

    await user.click(await products.findByRole('button', { name: 'Add Product' }))
    await user.type(products.getByLabelText('Product name'), 'Strawberries')
    await user.selectOptions(products.getByLabelText('Category'), 'Fruits')
    await user.type(products.getByLabelText('Price'), price)
    await user.selectOptions(products.getByLabelText('Sold by'), 'pint')
    await user.click(products.getByRole('button', { name: 'Add Product' }))

    expect(await products.findByRole('alert')).toHaveTextContent(expectedMessage)
    expect(api.requestsTo('POST', '/api/products')).toHaveLength(0)
  })

  it('rejects an availability window that ends before it starts', async () => {
    const api = openDashboard([])
    const user = userEvent.setup()
    const products = await findProductsSection()

    await user.click(await products.findByRole('button', { name: 'Add Product' }))
    await user.type(products.getByLabelText('Product name'), 'Strawberries')
    await user.selectOptions(products.getByLabelText('Category'), 'Fruits')
    await user.type(products.getByLabelText('Price'), '5.25')
    await user.selectOptions(products.getByLabelText('Sold by'), 'pint')
    await user.type(products.getByLabelText('Available from'), '2026-07-10')
    await user.type(products.getByLabelText('Available until'), '2026-07-01')
    await user.click(products.getByRole('button', { name: 'Add Product' }))

    expect(await products.findByRole('alert')).toHaveTextContent(
      'Available until must not be before available from.',
    )
    expect(api.requestsTo('POST', '/api/products')).toHaveLength(0)
  })
})

describe('managing an existing product', () => {
  it('updates stock through the inventory endpoint', async () => {
    const api = openDashboard()
    const user = userEvent.setup()
    const products = await findProductsSection()

    const stockInput = await products.findByLabelText('Stock for Heirloom Tomatoes')
    expect(stockInput).toHaveValue('20')
    await user.clear(stockInput)
    await user.type(stockInput, '35')
    await user.click(products.getByRole('button', { name: 'Update stock' }))

    expect(await products.findByText('35 lb in stock')).toBeInTheDocument()
    expect(products.getByText('Stock for Heirloom Tomatoes has been updated.')).toBeInTheDocument()
    expect(api.requestsTo('PATCH', '/api/products/11/inventory')).toEqual([
      { method: 'PATCH', path: '/api/products/11/inventory', body: { quantity_available: 35 } },
    ])
  })

  it.each(['-5', '2.5', 'lots', ''])(
    'rejects the stock value "%s" without calling the API',
    async (stock) => {
      const api = openDashboard()
      const user = userEvent.setup()
      const products = await findProductsSection()

      const stockInput = await products.findByLabelText('Stock for Heirloom Tomatoes')
      await user.clear(stockInput)
      if (stock !== '') {
        await user.type(stockInput, stock)
      }
      await user.click(products.getByRole('button', { name: 'Update stock' }))

      expect(await products.findByRole('alert')).toHaveTextContent(
        'Stock must be a whole number, zero or more.',
      )
      expect(api.requestsTo('PATCH', '/api/products/11/inventory')).toHaveLength(0)
    },
  )

  it('shows the server message when a stock update fails', async () => {
    const api = openDashboard()
    api.failNextRequest('PATCH', '/api/products/11/inventory', 500, 'Internal Server Error')
    const user = userEvent.setup()
    const products = await findProductsSection()

    const stockInput = await products.findByLabelText('Stock for Heirloom Tomatoes')
    await user.clear(stockInput)
    await user.type(stockInput, '5')
    await user.click(products.getByRole('button', { name: 'Update stock' }))

    expect(await products.findByRole('alert')).toHaveTextContent('Internal Server Error')
    expect(products.getByText('20 lb in stock')).toBeInTheDocument()
  })

  it('edits the details without sending stock', async () => {
    const api = openDashboard()
    const user = userEvent.setup()
    const products = await findProductsSection()

    await user.click(await products.findByRole('button', { name: 'Edit Heirloom Tomatoes' }))
    expect(products.getByLabelText('Product name')).toHaveValue('Heirloom Tomatoes')
    expect(products.getByLabelText('Price')).toHaveValue('4.50')
    expect(products.queryByLabelText('Quantity available')).not.toBeInTheDocument()

    await user.clear(products.getByLabelText('Price'))
    await user.type(products.getByLabelText('Price'), '5.00')
    await user.click(products.getByRole('button', { name: 'Save product' }))

    expect(await products.findByText('Heirloom Tomatoes has been saved.')).toBeInTheDocument()
    expect(products.getByText('Vegetables · $5.00 / lb')).toBeInTheDocument()
    expect(api.requestsTo('PUT', '/api/products/11')[0].body).toEqual({
      name: 'Heirloom Tomatoes',
      category: 'VEGETABLES',
      description: 'Vine-ripened, picked this week.',
      price: '5.00',
      unit: 'LB',
      harvest_date: null,
      available_from: null,
      available_until: null,
      organic: true,
      active: true,
    })
  })

  it('deactivates and reactivates a product', async () => {
    const api = openDashboard()
    const user = userEvent.setup()
    const products = await findProductsSection()

    await user.click(await products.findByRole('button', { name: 'Deactivate Heirloom Tomatoes' }))

    expect(await products.findByText('Hidden from customers')).toBeInTheDocument()
    expect(
      products.getByText('Heirloom Tomatoes is now hidden from customers.'),
    ).toBeInTheDocument()
    expect(api.requestsTo('PUT', '/api/products/11')[0].body).toMatchObject({
      name: 'Heirloom Tomatoes',
      active: false,
    })

    await user.click(products.getByRole('button', { name: 'Activate Heirloom Tomatoes' }))

    expect(
      await products.findByText('Heirloom Tomatoes is visible to customers again.'),
    ).toBeInTheDocument()
    expect(products.queryByText('Hidden from customers')).not.toBeInTheDocument()
    expect(api.requestsTo('PUT', '/api/products/11')[1].body).toMatchObject({ active: true })
  })
})
