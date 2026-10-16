import { expect, test, type Page } from '@playwright/test'

import {
  cardTitled,
  createFarm,
  daysFromToday,
  logInThroughUi,
  newPerson,
  registerThroughUi,
  section,
  uniqueEmail,
} from './support.ts'

const CROP = 'Purple Okra'

// A customer location a few hundred meters from the farm below.
const CUSTOMER_LATITUDE = '35.230'
const CUSTOMER_LONGITUDE = '-80.840'

/** Searches for nearby grow offers as a customer and joins the one for CROP. */
async function commitTo(page: Page, quantity: string) {
  await page.goto('/customer/grow-offers')
  await page.getByLabel('Latitude', { exact: true }).fill(CUSTOMER_LATITUDE)
  await page.getByLabel('Longitude', { exact: true }).fill(CUSTOMER_LONGITUDE)
  await page.getByRole('button', { name: 'Search', exact: true }).click()

  const offer = cardTitled(page, CROP, section(page, 'Grow offers found'))
  await offer.getByRole('button', { name: `Join grow offer for ${CROP}` }).click()
  await offer.getByLabel('Quantity (lb)').fill(quantity)
  await offer.getByRole('button', { name: 'Commit', exact: true }).click()
  await expect(offer.getByRole('status')).toHaveText(`You committed to ${quantity} lb of this crop.`)
  return offer
}

test('customer demand leads to a grow offer that is confirmed once enough customers commit', async ({
  browser,
  request,
}) => {
  const farm = await createFarm(request, {
    farmName: 'Queen City Growers',
    city: 'Charlotte',
    zipCode: '28202',
    location: { latitude: 35.2271, longitude: -80.8431 },
  })

  // A customer asks for a crop no nearby farm sells.
  const firstCustomer = await newPerson(browser)
  await registerThroughUi(firstCustomer, {
    name: 'Avery First',
    email: uniqueEmail('first-customer'),
    role: 'CUSTOMER',
  })
  await firstCustomer.goto('/customer/crop-requests')
  await firstCustomer.getByLabel('Crop', { exact: true }).fill('purple okra')
  await firstCustomer.getByLabel('Quantity', { exact: true }).fill('2')
  await firstCustomer.getByLabel('Unit', { exact: true }).selectOption('LB')
  await firstCustomer.getByLabel('Latitude', { exact: true }).fill(CUSTOMER_LATITUDE)
  await firstCustomer.getByLabel('Longitude', { exact: true }).fill(CUSTOMER_LONGITUDE)
  await firstCustomer.getByRole('button', { name: 'Request this crop' }).click()
  await expect(firstCustomer.getByText(`Your request for ${CROP} has been sent.`)).toBeVisible()

  // The farmer sees the demand as a total, without who asked.
  const farmer = await newPerson(browser)
  await logInThroughUi(farmer, farm.farmerEmail, 'FARMER')
  await farmer.goto('/farmer/grow-on-demand')
  const demand = cardTitled(farmer, CROP, section(farmer, 'Local demand'))
  await expect(demand).toContainText('1 customer interested')
  await expect(demand).toContainText('2 lb/week estimated demand')
  await expect(demand).not.toContainText('Avery')

  // The farmer offers to grow it if two customers commit.
  await demand.getByRole('button', { name: `Create grow offer for ${CROP}` }).click()
  await expect(farmer.getByLabel('Crop', { exact: true })).toHaveValue(CROP)
  await farmer.getByLabel('Expected quantity', { exact: true }).fill('40')
  await farmer.getByLabel('Estimated price', { exact: true }).fill('3.50')
  await farmer.getByLabel('Planting date', { exact: true }).fill(daysFromToday(7))
  await farmer.getByLabel('Expected harvest date', { exact: true }).fill(daysFromToday(70))
  await farmer.getByLabel('Minimum customers', { exact: true }).fill('2')
  await farmer.getByRole('button', { name: 'Create offer' }).click()

  await expect(farmer.getByText(`Your grow offer for ${CROP} is open for commitments.`)).toBeVisible()
  const farmerOffer = cardTitled(farmer, CROP, section(farmer, 'Your grow offers'))
  await expect(farmerOffer.getByText('Open', { exact: true })).toBeVisible()
  await expect(farmerOffer).toContainText('0 / 2 customers committed')

  // The first commitment is not enough on its own.
  const firstView = await commitTo(firstCustomer, '2')
  await expect(firstView).toContainText('1 / 2 customers committed')
  await expect(firstView.getByText('Open', { exact: true })).toBeVisible()

  // A second customer commits and the threshold is reached.
  const secondCustomer = await newPerson(browser)
  await registerThroughUi(secondCustomer, {
    name: 'Blake Second',
    email: uniqueEmail('second-customer'),
    role: 'CUSTOMER',
  })
  const secondView = await commitTo(secondCustomer, '3')
  await expect(secondView).toContainText('2 / 2 customers committed')
  await expect(secondView.getByText('Confirmed', { exact: true })).toBeVisible()

  // Everyone involved now sees the offer as confirmed.
  await farmer.reload()
  const confirmedOffer = cardTitled(farmer, CROP, section(farmer, 'Your grow offers'))
  await expect(confirmedOffer.getByText('Confirmed', { exact: true })).toBeVisible()
  await expect(confirmedOffer).toContainText('2 / 2 customers committed')
  await expect(confirmedOffer).toContainText('5 of 40 lb spoken for')

  await firstCustomer.reload()
  const firstCommitment = cardTitled(firstCustomer, CROP, section(firstCustomer, 'My commitments'))
  await expect(firstCommitment.getByText('Confirmed', { exact: true })).toBeVisible()
  await expect(firstCommitment).toContainText('You committed to 2 lb')
})
