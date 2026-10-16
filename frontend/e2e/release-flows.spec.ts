import { expect, test, type Page } from '@playwright/test'

import {
  addProductThroughUi,
  cardTitled,
  createFarmThroughUi,
  daysFromToday,
  logInThroughUi,
  logOut,
  newPerson,
  registerThroughUi,
  section,
  uniqueEmail,
  updateStockThroughUi,
} from './support.ts'

// The complete farmer and customer flows, in the order they meet: the
// customer reserves what the farmer listed, asks for a crop nobody sells,
// and the farmer answers that demand with a grow offer the customer joins
// and then follows to harvest.

const FARM_NAME = 'Oak City Harvest'
const PRODUCT = 'Cherry Tomatoes'
const EVENT_TITLE = 'Sunflower Farm Tour'
const MISSING_CROP = 'Bok Choy'

// Raleigh. The customer is a few hundred meters from the farm, and no farm
// from the other browser tests is within 25 miles.
const CUSTOMER_LOCATION = { latitude: '35.775', longitude: '-78.640' }

async function fillLocation(page: Page) {
  await page.getByLabel('Latitude', { exact: true }).fill(CUSTOMER_LOCATION.latitude)
  await page.getByLabel('Longitude', { exact: true }).fill(CUSTOMER_LOCATION.longitude)
}

async function openTab(page: Page, dashboard: 'Customer' | 'Farmer', tab: string) {
  await page
    .getByRole('navigation', { name: `${dashboard} dashboard sections` })
    .getByRole('link', { name: tab, exact: true })
    .click()
}

test('a farmer and a customer complete every step of their flows', async ({ browser }) => {
  test.setTimeout(120_000)
  const farmer = await newPerson(browser)
  const customer = await newPerson(browser)
  const farmerEmail = uniqueEmail('release-farmer')
  const customerEmail = uniqueEmail('release-customer')

  await test.step('Farmer: register and log in', async () => {
    await registerThroughUi(farmer, { name: 'Morgan Fields', email: farmerEmail, role: 'FARMER' })
    await logOut(farmer)
    await logInThroughUi(farmer, farmerEmail, 'FARMER')
  })

  await test.step('Farmer: create the farm, a product and its stock', async () => {
    await createFarmThroughUi(farmer, {
      name: FARM_NAME,
      address: '12 Pullen Road',
      city: 'Raleigh',
      zipCode: '27607',
      latitude: '35.7796',
      longitude: '-78.6382',
    })
    await addProductThroughUi(farmer, { name: PRODUCT, price: '5.00', unit: 'LB', quantity: '10' })
    await updateStockThroughUi(farmer, PRODUCT, '25')
    await expect(cardTitled(farmer, PRODUCT)).toContainText('25 lb in stock')
  })

  await test.step('Farmer: create a farm event', async () => {
    await openTab(farmer, 'Farmer', 'Farm events')
    await farmer.getByRole('button', { name: 'Create Farm Event' }).click()
    await farmer.getByLabel('Event title', { exact: true }).fill(EVENT_TITLE)
    await farmer.getByLabel('Type of event', { exact: true }).selectOption('FARM_TOUR')
    await farmer.getByLabel('Event date', { exact: true }).fill(daysFromToday(10))
    await farmer.getByLabel('Start time', { exact: true }).fill('10:00')
    await farmer.getByLabel('End time', { exact: true }).fill('12:00')
    await farmer.getByLabel('Price per person', { exact: true }).fill('8.00')
    await farmer.getByLabel('Capacity', { exact: true }).fill('12')
    await farmer.getByRole('button', { name: 'Create event' }).click()
    await expect(farmer.getByText(`${EVENT_TITLE} has been created.`)).toBeVisible()
  })

  await test.step('Customer: register and log in', async () => {
    await registerThroughUi(customer, { name: 'Riley Shopper', email: customerEmail, role: 'CUSTOMER' })
    await logOut(customer)
    await logInThroughUi(customer, customerEmail, 'CUSTOMER')
  })

  await test.step('Customer: search by location with a chosen radius and reserve the product', async () => {
    await customer.getByLabel('Search term').fill('tomatoes')
    await fillLocation(customer)
    await customer.getByLabel('Radius', { exact: true }).selectOption({ label: '10 miles' })
    await customer.getByRole('button', { name: 'Search', exact: true }).click()
    await expect(customer.getByText('1 product within 10 miles')).toBeVisible()

    const result = cardTitled(customer, PRODUCT, section(customer, 'Search results'))
    await expect(result).toContainText(FARM_NAME)
    await result.getByRole('button', { name: `Reserve ${PRODUCT}` }).click()
    await result.getByLabel('Quantity (lb)').fill('4')
    await result.getByRole('button', { name: 'Confirm reservation' }).click()
    await expect(result.getByRole('status')).toContainText('Reserved 4 lb for pickup on')
    await expect(result).toContainText('21 lb')
  })

  await test.step('Customer: reserve the farm event', async () => {
    await openTab(customer, 'Customer', 'Farm experiences')
    await fillLocation(customer)
    await customer.getByRole('button', { name: 'Search', exact: true }).click()

    const event = cardTitled(customer, EVENT_TITLE, section(customer, 'Farm experiences found'))
    await event.getByRole('button', { name: `Reserve ${EVENT_TITLE}` }).click()
    await event.getByLabel('Party size').fill('3')
    await event.getByRole('button', { name: 'Confirm reservation' }).click()
    await expect(event.getByRole('status')).toContainText('Reserved for a party of 3.')

    await openTab(customer, 'Customer', 'My reservations')
    await expect(cardTitled(customer, PRODUCT, section(customer, 'Product reservations'))).toContainText('Pending')
    await expect(
      cardTitled(customer, EVENT_TITLE, section(customer, 'Farm experience reservations')),
    ).toContainText('Party of 3')
  })

  await test.step('Customer: request a crop the search cannot find', async () => {
    await openTab(customer, 'Customer', 'Products')
    await customer.getByLabel('Search term').fill('bok choy')
    await fillLocation(customer)
    await customer.getByRole('button', { name: 'Search', exact: true }).click()
    await expect(customer.getByText('No nearby farms currently have this crop.')).toBeVisible()

    // The empty search leads straight to a request for the same crop.
    await customer.getByRole('link', { name: 'Request this crop' }).click()
    await expect(customer).toHaveURL(/\/customer\/crop-requests$/)
    await expect(customer.getByLabel('Crop', { exact: true })).toHaveValue('bok choy')
    await expect(customer.getByLabel('Latitude', { exact: true })).toHaveValue(CUSTOMER_LOCATION.latitude)
    await customer.getByLabel('Quantity', { exact: true }).fill('2')
    await customer.getByLabel('Unit', { exact: true }).selectOption('BUNCH')
    await customer.getByRole('button', { name: 'Request this crop' }).click()
    await expect(customer.getByText(`Your request for ${MISSING_CROP} has been sent.`)).toBeVisible()
  })

  await test.step('Farmer: view local demand and create a grow offer', async () => {
    await openTab(farmer, 'Farmer', 'Grow-On-Demand')
    const demand = cardTitled(farmer, MISSING_CROP, section(farmer, 'Local demand'))
    await expect(demand).toContainText('1 customer interested')
    await expect(demand).toContainText('2 bunch/week estimated demand')

    await demand.getByRole('button', { name: `Create grow offer for ${MISSING_CROP}` }).click()
    await farmer.getByLabel('Expected quantity', { exact: true }).fill('30')
    await farmer.getByLabel('Estimated price', { exact: true }).fill('2.75')
    await farmer.getByLabel('Planting date', { exact: true }).fill(daysFromToday(5))
    await farmer.getByLabel('Expected harvest date', { exact: true }).fill(daysFromToday(60))
    await farmer.getByLabel('Minimum customers', { exact: true }).fill('1')
    await farmer.getByRole('button', { name: 'Create offer' }).click()
    await expect(farmer.getByText(`Your grow offer for ${MISSING_CROP} is open for commitments.`)).toBeVisible()
  })

  await test.step('Customer: join the grow offer, which confirms it', async () => {
    await openTab(customer, 'Customer', 'Grow offers')
    await fillLocation(customer)
    await customer.getByRole('button', { name: 'Search', exact: true }).click()

    const offer = cardTitled(customer, MISSING_CROP, section(customer, 'Grow offers found'))
    await offer.getByRole('button', { name: `Join grow offer for ${MISSING_CROP}` }).click()
    await offer.getByLabel('Quantity (bunch)').fill('2')
    await offer.getByRole('button', { name: 'Commit', exact: true }).click()
    await expect(offer.getByRole('status')).toHaveText(`You committed to 2 bunch of this crop.`)
    await expect(offer.getByText('Confirmed', { exact: true })).toBeVisible()
  })

  await test.step('Customer: receive the confirmation notification', async () => {
    await customer.goto('/notifications')
    await expect(customer.getByRole('link', { name: 'Notifications, 1 unread' })).toBeVisible()
    await expect(
      customer.getByText(`${MISSING_CROP} at ${FARM_NAME} is confirmed. Enough customers committed, so the farm will grow it.`),
    ).toBeVisible()
  })

  await test.step('Farmer: post a crop update', async () => {
    await farmer.reload()
    const farmerOffer = cardTitled(farmer, MISSING_CROP, section(farmer, 'Your grow offers'))
    await expect(farmerOffer.getByText('Confirmed', { exact: true })).toBeVisible()
    await farmerOffer.getByRole('link', { name: `Crop journey for ${MISSING_CROP}` }).click()

    await farmer.getByLabel('Stage', { exact: true }).selectOption('PLANTED')
    await farmer.getByLabel('Message', { exact: true }).fill('Seedlings are in the ground and watered.')
    await farmer.getByRole('button', { name: 'Post Crop Update' }).click()
    await expect(
      farmer.getByText('Your update has been posted and committed customers have been notified.'),
    ).toBeVisible()
  })

  await test.step('Customer: receive the update notification and view the crop journey', async () => {
    await customer.reload()
    await expect(customer.getByRole('link', { name: 'Notifications, 2 unread' })).toBeVisible()
    await expect(
      customer.getByText(`${FARM_NAME} posted an update: your ${MISSING_CROP} has been planted.`),
    ).toBeVisible()

    await customer.goto('/customer/grow-offers')
    const commitment = cardTitled(customer, MISSING_CROP, section(customer, 'My commitments'))
    await expect(commitment.getByText('Growing', { exact: true })).toBeVisible()
    await commitment.getByRole('link', { name: `View crop journey for ${MISSING_CROP}` }).click()

    const journey = section(customer, 'Crop journey')
    await expect(journey.getByRole('heading', { name: 'Planted' })).toBeVisible()
    await expect(journey).toContainText('Seedlings are in the ground and watered.')
    // Customers follow the journey; only the farmer can post to it.
    await expect(customer.getByRole('button', { name: 'Post Crop Update' })).toHaveCount(0)
  })
})
