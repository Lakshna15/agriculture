import { expect, test } from '@playwright/test'

import {
  addProduct,
  cardTitled,
  createFarm,
  logInThroughUi,
  logOut,
  registerThroughUi,
  section,
  uniqueEmail,
} from './support.ts'

const PRODUCT_NAME = 'Heirloom Tomatoes'

test('a customer registers, logs in, finds a nearby product, reserves it and sees the reservation', async ({
  page,
  request,
}) => {
  const farm = await createFarm(request, {
    farmName: 'Riverbend Farm',
    city: 'Asheville',
    zipCode: '28801',
    location: { latitude: 35.5951, longitude: -82.5515 },
  })
  await addProduct(request, farm, { productName: PRODUCT_NAME, quantity: 20 })

  const email = uniqueEmail('customer')
  await registerThroughUi(page, { name: 'Casey Customer', email, role: 'CUSTOMER' })
  await logOut(page)
  await logInThroughUi(page, email, 'CUSTOMER')

  // Search from a point a few hundred meters from the farm.
  await page.getByLabel('Search term').fill('tomatoes')
  await page.getByLabel('Latitude', { exact: true }).fill('35.598')
  await page.getByLabel('Longitude', { exact: true }).fill('-82.555')
  await page.getByRole('button', { name: 'Search', exact: true }).click()

  await expect(page.getByText('1 product within 25 miles')).toBeVisible()
  const result = cardTitled(page, PRODUCT_NAME, section(page, 'Search results'))
  await expect(result).toContainText('Riverbend Farm')
  await expect(result).toContainText('$4.50')
  await expect(result).toContainText('20 lb')

  // Reserve part of the stock for pickup today.
  await result.getByRole('button', { name: `Reserve ${PRODUCT_NAME}` }).click()
  await result.getByLabel('Quantity (lb)').fill('3')
  await result.getByRole('button', { name: 'Confirm reservation' }).click()

  await expect(result.getByRole('status')).toContainText('Reserved 3 lb for pickup on')
  await expect(result).toContainText('17 lb')

  // The reservation is listed with the farm's pickup details.
  await result.getByRole('link', { name: 'View my reservations' }).click()
  await expect(page).toHaveURL(/\/customer\/reservations$/)
  const reservation = cardTitled(page, PRODUCT_NAME, section(page, 'Product reservations'))
  await expect(reservation).toContainText('Pending')
  await expect(reservation).toContainText('3 lb · Pickup')
  await expect(reservation).toContainText('Riverbend Farm, 1 Orchard Lane, Asheville, NC 28801')

  // It is stored, not just shown: it is still there after a reload.
  await page.reload()
  await expect(reservation).toContainText('Pending')
})
