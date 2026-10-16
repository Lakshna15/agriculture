import { expect, test } from '@playwright/test'

import {
  addProductThroughUi,
  cardTitled,
  createFarmThroughUi,
  logInThroughUi,
  logOut,
  registerThroughUi,
  uniqueEmail,
  updateStockThroughUi,
} from './support.ts'

const FARM_NAME = 'Piedmont Greens'
const PRODUCT_NAME = 'Rainbow Chard'

test('a farmer registers, logs in, creates a farm, lists a product and updates its stock', async ({
  page,
}) => {
  const email = uniqueEmail('farmer')
  await registerThroughUi(page, { name: 'Fran Farmer', email, role: 'FARMER' })
  await logOut(page)
  await logInThroughUi(page, email, 'FARMER')

  await createFarmThroughUi(page, {
    name: FARM_NAME,
    address: '220 Meadow Road',
    city: 'Greensboro',
    zipCode: '27401',
    latitude: '36.0726',
    longitude: '-79.792',
  })

  // List a product with some opening stock.
  await addProductThroughUi(page, { name: PRODUCT_NAME, price: '3.25', unit: 'BUNCH', quantity: '12' })
  const product = cardTitled(page, PRODUCT_NAME)
  await expect(product).toContainText('$3.25 / bunch')
  await expect(product).toContainText('12 bunch in stock')

  // Update the inventory.
  await updateStockThroughUi(page, PRODUCT_NAME, '30')
  await expect(cardTitled(page, PRODUCT_NAME)).toContainText('30 bunch in stock')

  // The farm, the product and the new stock level are all stored.
  await page.reload()
  await expect(page.getByRole('heading', { name: FARM_NAME })).toBeVisible()
  await expect(cardTitled(page, PRODUCT_NAME)).toContainText('30 bunch in stock')
})
