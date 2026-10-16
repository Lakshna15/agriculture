import {
  expect,
  type APIRequestContext,
  type Browser,
  type Locator,
  type Page,
} from '@playwright/test'

/** Every account in the browser tests uses this password. They exist only in the throwaway e2e database. */
export const TEST_PASSWORD = 'e2e-test-password'

let emailCounter = 0

/** An address no other test in the run has used. */
export function uniqueEmail(prefix: string): string {
  emailCounter += 1
  return `${prefix}-${Date.now()}-${emailCounter}@example.com`
}

type Role = 'CUSTOMER' | 'FARMER'

const dashboardPath: Record<Role, RegExp> = {
  CUSTOMER: /\/customer$/,
  FARMER: /\/farmer$/,
}

export async function registerThroughUi(
  page: Page,
  account: { name: string; email: string; role: Role },
): Promise<void> {
  await page.goto('/register')
  await page.getByLabel('Name', { exact: true }).fill(account.name)
  await page.getByLabel('Email', { exact: true }).fill(account.email)
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD)
  await page
    .getByRole('radio', { name: account.role === 'FARMER' ? /^Farmer/ : /^Customer/ })
    .check()
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).toHaveURL(dashboardPath[account.role])
}

export async function logInThroughUi(page: Page, email: string, role: Role): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD)
  await page.getByRole('button', { name: 'Login', exact: true }).click()
  await expect(page).toHaveURL(dashboardPath[role])
}

export async function logOut(page: Page): Promise<void> {
  const accountNavigation = page.getByRole('navigation', { name: 'Account' })
  await accountNavigation.getByRole('button', { name: 'Logout' }).click()
  await expect(accountNavigation.getByRole('link', { name: 'Login', exact: true })).toBeVisible()
}

/**
 * A list item identified by the heading inside it, such as a product or offer
 * card, optionally only within one section of the page.
 */
export function cardTitled(page: Page, title: string, within: Page | Locator = page): Locator {
  return within
    .getByRole('listitem')
    .filter({ has: page.getByRole('heading', { name: title, exact: true }) })
}

/** A page section, found by its heading. */
export function section(page: Page, heading: string): Locator {
  return page.getByRole('region', { name: heading, exact: true })
}

/** A separate browser session, so each person has their own sign-in. */
export async function newPerson(browser: Browser): Promise<Page> {
  const context = await browser.newContext()
  return context.newPage()
}

/** An ISO calendar date the given number of days from today. */
export function daysFromToday(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() + days)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

type FarmDetails = {
  name: string
  address: string
  city: string
  zipCode: string
  latitude: string
  longitude: string
}

/** Creates the signed-in farmer's farm from the empty farm page. */
export async function createFarmThroughUi(page: Page, farm: FarmDetails): Promise<void> {
  await expect(page.getByRole('heading', { name: 'You have not set up your farm yet' })).toBeVisible()
  await page.getByRole('button', { name: 'Create Farm' }).click()
  await page.getByLabel('Farm name', { exact: true }).fill(farm.name)
  await page.getByLabel('Street address', { exact: true }).fill(farm.address)
  await page.getByLabel('City', { exact: true }).fill(farm.city)
  await page.getByLabel('State', { exact: true }).selectOption('NC')
  await page.getByLabel('ZIP code', { exact: true }).fill(farm.zipCode)
  await page.getByLabel('Latitude', { exact: true }).fill(farm.latitude)
  await page.getByLabel('Longitude', { exact: true }).fill(farm.longitude)
  await page.getByRole('button', { name: 'Create Farm' }).click()

  await expect(page.getByText('Your farm has been created.')).toBeVisible()
  await expect(page.getByRole('heading', { name: farm.name })).toBeVisible()
  await expect(page.getByText(`${farm.address}, ${farm.city}, NC ${farm.zipCode}`)).toBeVisible()
}

type ProductDetails = { name: string; price: string; unit: string; quantity: string }

/** Lists a product on the signed-in farmer's farm page. */
export async function addProductThroughUi(page: Page, product: ProductDetails): Promise<void> {
  await page.getByRole('button', { name: 'Add Product' }).click()
  await page.getByLabel('Product name', { exact: true }).fill(product.name)
  await page.getByLabel('Category', { exact: true }).selectOption('VEGETABLES')
  await page.getByLabel('Price', { exact: true }).fill(product.price)
  await page.getByLabel('Sold by', { exact: true }).selectOption(product.unit)
  await page.getByLabel('Quantity available', { exact: true }).fill(product.quantity)
  await page.getByRole('button', { name: 'Add Product' }).click()

  await expect(page.getByText(`${product.name} has been added.`)).toBeVisible()
}

/** Sets a product's stock from the farmer's product list. */
export async function updateStockThroughUi(page: Page, productName: string, quantity: string): Promise<void> {
  const product = cardTitled(page, productName)
  await product.getByLabel(`Stock for ${productName}`).fill(quantity)
  await product.getByRole('button', { name: 'Update stock' }).click()

  await expect(page.getByText(`Stock for ${productName} has been updated.`)).toBeVisible()
}

type FarmLocation = { latitude: number; longitude: number }

async function accessTokenFor(request: APIRequestContext, email: string): Promise<string> {
  const response = await request.post('/api/auth/login', {
    data: { email, password: TEST_PASSWORD },
  })
  expect(response.status()).toBe(200)
  const body = (await response.json()) as { access_token: string }
  return body.access_token
}

type SeededFarm = { farmerEmail: string; headers: Record<string, string> }

/**
 * Sets up a farmer and a farm through the API, for flows that start once a
 * farm already exists. Returns the farmer's email so the test can log in as them.
 */
export async function createFarm(
  request: APIRequestContext,
  details: { farmName: string; city: string; zipCode: string; location: FarmLocation },
): Promise<SeededFarm> {
  const farmerEmail = uniqueEmail('seeded-farmer')
  const registration = await request.post('/api/auth/register', {
    data: { name: 'Sam Seeded', email: farmerEmail, password: TEST_PASSWORD, role: 'FARMER' },
  })
  expect(registration.status()).toBe(201)
  const headers = { Authorization: `Bearer ${await accessTokenFor(request, farmerEmail)}` }

  const farm = await request.post('/api/farms', {
    headers,
    data: {
      farm_name: details.farmName,
      description: null,
      address: '1 Orchard Lane',
      city: details.city,
      state: 'NC',
      zip_code: details.zipCode,
      latitude: details.location.latitude,
      longitude: details.location.longitude,
      phone: null,
      pickup_available: true,
      delivery_available: false,
    },
  })
  expect(farm.status()).toBe(201)
  return { farmerEmail, headers }
}

/** Lists a product on a farm created by createFarm. */
export async function addProduct(
  request: APIRequestContext,
  farm: SeededFarm,
  details: { productName: string; quantity: number },
): Promise<void> {
  const product = await request.post('/api/products', {
    headers: farm.headers,
    data: {
      name: details.productName,
      category: 'VEGETABLES',
      description: null,
      price: '4.50',
      unit: 'LB',
      harvest_date: null,
      available_from: null,
      available_until: null,
      organic: false,
      active: true,
      quantity_available: details.quantity,
    },
  })
  expect(product.status()).toBe(201)
}
