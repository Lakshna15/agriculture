import { vi } from 'vitest'
import type { User, UserRole } from '../api/auth.ts'
import type {
  EventReservation,
  EventSearchResult,
  FarmEvent,
  NewFarmEvent,
} from '../api/events.ts'
import type { Farm, FarmDetails } from '../api/farms.ts'
import type { NewProduct, Product, ProductDetails, ProductSearchResult } from '../api/products.ts'
import type {
  NewProductReservation,
  ProductReservation,
  ReservationFarm,
  ReservationStatus,
} from '../api/reservations.ts'
import { ACCESS_TOKEN_STORAGE_KEY } from '../auth/tokenStorage.ts'

type FakeAccount = { user: User; password: string }

type RecordedRequest = { method: string; path: string; body: unknown }

type ForcedFailure = { method: string; path: string; status: number; detail: string }

type InitialData = {
  accounts?: FakeAccount[]
  farms?: Farm[]
  products?: Product[]
  /** Returned as-is by every search; the fake does not filter or sort. */
  searchResults?: ProductSearchResult[]
  /**
   * Reservation lists are returned whole to whoever asks. Each test signs in
   * one customer or one farmer, so the fake does not track who owns what.
   */
  productReservations?: ProductReservation[]
  events?: FarmEvent[]
  eventSearchResults?: EventSearchResult[]
  eventReservations?: EventReservation[]
}

const TIMESTAMP = '2026-01-01T00:00:00Z'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function buildUser(overrides: Partial<User> & { role: UserRole }): User {
  return {
    id: 1,
    name: 'Ana Grower',
    email: 'ana@example.com',
    created_at: TIMESTAMP,
    updated_at: TIMESTAMP,
    ...overrides,
  }
}

export function buildFarm(overrides: Partial<Farm> & { owner_id: number }): Farm {
  return {
    id: 1,
    farm_name: 'Green Acres',
    description: 'Family-run vegetable farm.',
    address: '100 Orchard Road',
    city: 'Charlotte',
    state: 'NC',
    zip_code: '28202',
    latitude: 35.2271,
    longitude: -80.8431,
    phone: '704-555-0100',
    pickup_available: true,
    delivery_available: false,
    created_at: TIMESTAMP,
    updated_at: TIMESTAMP,
    ...overrides,
  }
}

export function buildProduct(overrides: Partial<Product> & { farm_id: number }): Product {
  return {
    id: 1,
    name: 'Heirloom Tomatoes',
    category: 'VEGETABLES',
    description: 'Vine-ripened, picked this week.',
    price: '4.50',
    unit: 'LB',
    quantity_available: 20,
    harvest_date: null,
    available_from: null,
    available_until: null,
    organic: true,
    active: true,
    created_at: TIMESTAMP,
    updated_at: TIMESTAMP,
    ...overrides,
  }
}

export function buildSearchResult(
  overrides: {
    product?: Partial<ProductSearchResult['product']>
    farm?: Partial<ProductSearchResult['farm']>
  } & Partial<Omit<ProductSearchResult, 'product' | 'farm'>> = {},
): ProductSearchResult {
  const { product, farm, ...rest } = overrides
  return {
    product: {
      id: 1,
      name: 'Heirloom Tomatoes',
      category: 'VEGETABLES',
      description: 'Vine-ripened, picked this week.',
      unit: 'LB',
      organic: true,
      available_from: null,
      available_until: null,
      ...product,
    },
    farm: {
      id: 1,
      farm_name: 'Green Acres',
      city: 'Charlotte',
      state: 'NC',
      pickup_available: true,
      delivery_available: false,
      ...farm,
    },
    distance_miles: 3.2,
    price: '4.50',
    quantity_available: 20,
    harvest_date: '2026-06-01',
    ...rest,
  }
}

const RESERVATION_FARM: ReservationFarm = {
  id: 1,
  farm_name: 'Green Acres',
  address: '100 Orchard Road',
  city: 'Charlotte',
  state: 'NC',
  zip_code: '28202',
  phone: '704-555-0100',
}

export function buildProductReservation(
  overrides: Partial<ProductReservation> = {},
): ProductReservation {
  return {
    id: 1,
    quantity: 3,
    pickup_date: '2026-06-01',
    pickup_time: '10:30:00',
    status: 'PENDING',
    created_at: TIMESTAMP,
    updated_at: TIMESTAMP,
    customer_name: 'Ana Grower',
    product: { id: 1, name: 'Heirloom Tomatoes', unit: 'LB' },
    farm: RESERVATION_FARM,
    ...overrides,
  }
}

export function buildFarmEvent(overrides: Partial<FarmEvent> = {}): FarmEvent {
  return {
    id: 1,
    farm_id: 1,
    title: 'Strawberry Picking Morning',
    description: 'Pick your own strawberries straight from the field.',
    event_type: 'STRAWBERRY_PICKING',
    event_date: '2026-06-08',
    start_time: '09:00:00',
    end_time: '12:00:00',
    price: '12.00',
    capacity: 20,
    spots_remaining: 20,
    created_at: TIMESTAMP,
    ...overrides,
  }
}

export function buildEventSearchResult(
  overrides: { event?: Partial<FarmEvent>; farm?: Partial<EventSearchResult['farm']> } & Partial<
    Pick<EventSearchResult, 'distance_miles'>
  > = {},
): EventSearchResult {
  return {
    event: buildFarmEvent(overrides.event),
    farm: { id: 1, farm_name: 'Green Acres', city: 'Charlotte', state: 'NC', ...overrides.farm },
    distance_miles: overrides.distance_miles ?? 3.2,
  }
}

export function buildEventReservation(overrides: Partial<EventReservation> = {}): EventReservation {
  return {
    id: 1,
    party_size: 4,
    status: 'PENDING',
    created_at: TIMESTAMP,
    customer_name: 'Ana Grower',
    event: {
      id: 1,
      title: 'Strawberry Picking Morning',
      event_type: 'STRAWBERRY_PICKING',
      event_date: '2026-06-08',
      start_time: '09:00:00',
      end_time: '12:00:00',
      price: '12.00',
    },
    farm: RESERVATION_FARM,
    ...overrides,
  }
}

/**
 * Replaces fetch with an in-memory stand-in for the backend. It follows the
 * real API's status codes and error bodies so the tests exercise the same
 * paths the application takes against the server.
 */
export function installFakeApi(initial: InitialData = {}) {
  const accounts = [...(initial.accounts ?? [])]
  const farms = [...(initial.farms ?? [])]
  const products = [...(initial.products ?? [])]
  const searchResults = [...(initial.searchResults ?? [])]
  const productReservations = [...(initial.productReservations ?? [])]
  const events = [...(initial.events ?? [])]
  const eventSearchResults = [...(initial.eventSearchResults ?? [])]
  const eventReservations = [...(initial.eventReservations ?? [])]
  const usersByToken = new Map<string, User>()
  const requests: RecordedRequest[] = []
  const searches: Record<string, string>[] = []
  const eventSearches: Record<string, string>[] = []
  const forcedFailures: ForcedFailure[] = []

  function issueToken(user: User): string {
    const accessToken = `token-for-user-${user.id}-${usersByToken.size + 1}`
    usersByToken.set(accessToken, user)
    return accessToken
  }

  function handleAuthRequest(method: string, path: string, body: unknown, user: User | undefined) {
    if (method === 'POST' && path === '/api/auth/register') {
      const details = body as { name: string; email: string; password: string; role: UserRole }
      if (accounts.some((account) => account.user.email === details.email)) {
        return jsonResponse(409, { detail: 'An account with this email already exists' })
      }
      const newUser = buildUser({
        id: accounts.length + 1,
        name: details.name,
        email: details.email,
        role: details.role,
      })
      accounts.push({ user: newUser, password: details.password })
      return jsonResponse(201, newUser)
    }

    if (method === 'POST' && path === '/api/auth/login') {
      const credentials = body as { email: string; password: string }
      const account = accounts.find(
        (candidate) =>
          candidate.user.email === credentials.email && candidate.password === credentials.password,
      )
      if (!account) {
        return jsonResponse(401, { detail: 'Incorrect email or password' })
      }
      return jsonResponse(200, {
        access_token: issueToken(account.user),
        token_type: 'bearer',
        user: account.user,
      })
    }

    if (method === 'GET' && path === '/api/auth/me') {
      return user ? jsonResponse(200, user) : jsonResponse(401, { detail: 'Not authenticated' })
    }

    return null
  }

  function handleFarmRequest(method: string, path: string, body: unknown, user: User | undefined) {
    if (!path.startsWith('/api/farms')) {
      return null
    }
    if (!user) {
      return jsonResponse(401, { detail: 'Not authenticated' })
    }

    if (method === 'GET' && path === '/api/farms/me') {
      const farm = farms.find((candidate) => candidate.owner_id === user.id)
      return farm
        ? jsonResponse(200, farm)
        : jsonResponse(404, { detail: 'You have not created a farm yet' })
    }

    if (method === 'POST' && path === '/api/farms') {
      if (farms.some((candidate) => candidate.owner_id === user.id)) {
        return jsonResponse(409, { detail: 'You already have a farm' })
      }
      const farm = buildFarm({ ...(body as FarmDetails), id: farms.length + 1, owner_id: user.id })
      farms.push(farm)
      return jsonResponse(201, farm)
    }

    const farmIdMatch = /^\/api\/farms\/(\d+)$/.exec(path)
    if (method === 'PUT' && farmIdMatch) {
      const farmIndex = farms.findIndex((candidate) => candidate.id === Number(farmIdMatch[1]))
      if (farmIndex === -1) {
        return jsonResponse(404, { detail: 'Farm not found' })
      }
      if (farms[farmIndex].owner_id !== user.id) {
        return jsonResponse(403, { detail: 'You can only edit your own farm' })
      }
      farms[farmIndex] = { ...farms[farmIndex], ...(body as FarmDetails) }
      return jsonResponse(200, farms[farmIndex])
    }

    return null
  }

  function handleProductRequest(
    method: string,
    path: string,
    body: unknown,
    user: User | undefined,
  ) {
    if (!path.startsWith('/api/products')) {
      return null
    }
    if (method === 'GET' && path === '/api/products/search') {
      return jsonResponse(200, searchResults)
    }
    if (!user) {
      return jsonResponse(401, { detail: 'Not authenticated' })
    }

    const farm = farms.find((candidate) => candidate.owner_id === user.id)

    if (method === 'GET' && path === '/api/products/mine') {
      const ownProducts = products.filter((product) => product.farm_id === farm?.id)
      return jsonResponse(200, ownProducts)
    }

    if (method === 'POST' && path === '/api/products') {
      if (!farm) {
        return jsonResponse(409, { detail: 'Create your farm first' })
      }
      const product = buildProduct({
        ...(body as NewProduct),
        id: products.length + 1,
        farm_id: farm.id,
      })
      products.push(product)
      return jsonResponse(201, product)
    }

    const productMatch = /^\/api\/products\/(\d+)(\/inventory)?$/.exec(path)
    if (!productMatch) {
      return null
    }
    const productIndex = products.findIndex((product) => product.id === Number(productMatch[1]))
    if (productIndex === -1) {
      return jsonResponse(404, { detail: 'Product not found' })
    }
    if (products[productIndex].farm_id !== farm?.id) {
      return jsonResponse(403, { detail: 'You can only manage your own products' })
    }

    if (method === 'PUT' && !productMatch[2]) {
      products[productIndex] = { ...products[productIndex], ...(body as ProductDetails) }
      return jsonResponse(200, products[productIndex])
    }
    if (method === 'PATCH' && productMatch[2]) {
      const { quantity_available } = body as { quantity_available: number }
      products[productIndex] = { ...products[productIndex], quantity_available }
      return jsonResponse(200, products[productIndex])
    }
    return null
  }

  /** Applies a status change to one reservation in a list and returns the response. */
  function updateStatus<Reservation extends { id: number; status: ReservationStatus }>(
    reservations: Reservation[],
    reservationId: number,
    body: unknown,
  ) {
    const index = reservations.findIndex((reservation) => reservation.id === reservationId)
    if (index === -1) {
      return jsonResponse(404, { detail: 'Reservation not found' })
    }
    reservations[index] = { ...reservations[index], status: (body as { status: ReservationStatus }).status }
    return jsonResponse(200, reservations[index])
  }

  function handleProductReservationRequest(
    method: string,
    path: string,
    body: unknown,
    user: User | undefined,
  ) {
    if (!path.startsWith('/api/reservations')) {
      return null
    }
    if (!user) {
      return jsonResponse(401, { detail: 'Not authenticated' })
    }

    if (method === 'GET' && (path === '/api/reservations/mine' || path === '/api/reservations/farm')) {
      return jsonResponse(200, productReservations)
    }

    if (method === 'POST' && path === '/api/reservations') {
      const details = body as NewProductReservation
      const resultIndex = searchResults.findIndex(
        (result) => result.product.id === details.product_id,
      )
      if (resultIndex === -1) {
        return jsonResponse(404, { detail: 'Product not found' })
      }
      const result = searchResults[resultIndex]
      if (details.quantity > result.quantity_available) {
        return jsonResponse(409, { detail: `Only ${result.quantity_available} available` })
      }
      searchResults[resultIndex] = {
        ...result,
        quantity_available: result.quantity_available - details.quantity,
      }
      const reservation = buildProductReservation({
        id: productReservations.length + 1,
        quantity: details.quantity,
        pickup_date: details.pickup_date,
        pickup_time: details.pickup_time,
        customer_name: user.name,
        product: { id: result.product.id, name: result.product.name, unit: result.product.unit },
        farm: { ...RESERVATION_FARM, id: result.farm.id, farm_name: result.farm.farm_name },
      })
      productReservations.push(reservation)
      return jsonResponse(201, reservation)
    }

    const statusMatch = /^\/api\/reservations\/(\d+)\/status$/.exec(path)
    if (method === 'PATCH' && statusMatch) {
      return updateStatus(productReservations, Number(statusMatch[1]), body)
    }
    return null
  }

  function handleEventRequest(method: string, path: string, body: unknown, user: User | undefined) {
    if (!path.startsWith('/api/events')) {
      return null
    }
    if (method === 'GET' && path === '/api/events/search') {
      return jsonResponse(200, eventSearchResults)
    }
    if (!user) {
      return jsonResponse(401, { detail: 'Not authenticated' })
    }

    if (method === 'GET' && path === '/api/events/mine') {
      return jsonResponse(200, events)
    }

    if (method === 'POST' && path === '/api/events') {
      const farm = farms.find((candidate) => candidate.owner_id === user.id)
      if (!farm) {
        return jsonResponse(409, { detail: 'Create your farm first' })
      }
      const details = body as NewFarmEvent
      const event = buildFarmEvent({
        ...details,
        id: events.length + 1,
        farm_id: farm.id,
        spots_remaining: details.capacity,
      })
      events.push(event)
      return jsonResponse(201, event)
    }
    return null
  }

  function handleEventReservationRequest(
    method: string,
    path: string,
    body: unknown,
    user: User | undefined,
  ) {
    if (!path.startsWith('/api/event-reservations')) {
      return null
    }
    if (!user) {
      return jsonResponse(401, { detail: 'Not authenticated' })
    }

    if (
      method === 'GET' &&
      (path === '/api/event-reservations/mine' || path === '/api/event-reservations/farm')
    ) {
      return jsonResponse(200, eventReservations)
    }

    if (method === 'POST' && path === '/api/event-reservations') {
      const details = body as { event_id: number; party_size: number }
      const resultIndex = eventSearchResults.findIndex(
        (result) => result.event.id === details.event_id,
      )
      if (resultIndex === -1) {
        return jsonResponse(404, { detail: 'Event not found' })
      }
      const { event, farm } = eventSearchResults[resultIndex]
      if (details.party_size > event.spots_remaining) {
        return jsonResponse(409, { detail: `Only ${event.spots_remaining} spots remaining` })
      }
      eventSearchResults[resultIndex] = {
        ...eventSearchResults[resultIndex],
        event: { ...event, spots_remaining: event.spots_remaining - details.party_size },
      }
      const reservation = buildEventReservation({
        id: eventReservations.length + 1,
        party_size: details.party_size,
        customer_name: user.name,
        event: {
          id: event.id,
          title: event.title,
          event_type: event.event_type,
          event_date: event.event_date,
          start_time: event.start_time,
          end_time: event.end_time,
          price: event.price,
        },
        farm: { ...RESERVATION_FARM, id: farm.id, farm_name: farm.farm_name },
      })
      eventReservations.push(reservation)
      return jsonResponse(201, reservation)
    }

    const statusMatch = /^\/api\/event-reservations\/(\d+)\/status$/.exec(path)
    if (method === 'PATCH' && statusMatch) {
      return updateStatus(eventReservations, Number(statusMatch[1]), body)
    }
    return null
  }

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const path = url.pathname
    const method = init?.method ?? 'GET'
    const body: unknown = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
    requests.push({ method, path, body })
    if (path === '/api/products/search') {
      searches.push(Object.fromEntries(url.searchParams))
    }
    if (path === '/api/events/search') {
      eventSearches.push(Object.fromEntries(url.searchParams))
    }

    const failureIndex = forcedFailures.findIndex(
      (failure) => failure.method === method && failure.path === path,
    )
    if (failureIndex !== -1) {
      const [failure] = forcedFailures.splice(failureIndex, 1)
      return jsonResponse(failure.status, { detail: failure.detail })
    }

    const authorization = new Headers(init?.headers).get('Authorization') ?? ''
    const user = usersByToken.get(authorization.replace('Bearer ', ''))

    return (
      handleAuthRequest(method, path, body, user) ??
      handleFarmRequest(method, path, body, user) ??
      handleProductRequest(method, path, body, user) ??
      handleProductReservationRequest(method, path, body, user) ??
      handleEventRequest(method, path, body, user) ??
      handleEventReservationRequest(method, path, body, user) ??
      jsonResponse(404, { detail: 'Not Found' })
    )
  })

  vi.stubGlobal('fetch', fetchMock)

  return {
    requests,
    /** The query parameters of every product search, in order. */
    searches,
    /** The query parameters of every farm experience search, in order. */
    eventSearches,
    issueToken,
    /** Stores a valid token, as if the user had signed in before the page loaded. */
    signIn(user: User): void {
      window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, issueToken(user))
    },
    /** Makes the next matching request fail once with the given status and message. */
    failNextRequest(method: string, path: string, status: number, detail: string): void {
      forcedFailures.push({ method, path, status, detail })
    },
    requestsTo(method: string, path: string): RecordedRequest[] {
      return requests.filter((request) => request.method === method && request.path === path)
    },
  }
}
