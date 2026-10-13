import { vi } from 'vitest'
import type { User, UserRole } from '../api/auth.ts'
import type { CropStage, CropUpdate, NewCropUpdate } from '../api/cropJourney.ts'
import type { CropPoll, CropPollSearchResult, CropVote, NewCropPoll } from '../api/cropPolls.ts'
import type { CropDemand, CropRequest, NewCropRequest } from '../api/cropRequests.ts'
import type {
  EventReservation,
  EventSearchResult,
  FarmEvent,
  NewFarmEvent,
} from '../api/events.ts'
import type { Farm, FarmDetails } from '../api/farms.ts'
import type {
  CropCommitment,
  GrowOffer,
  GrowOfferSearchResult,
  NewGrowOffer,
} from '../api/growOffers.ts'
import type { Notification } from '../api/notifications.ts'
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
  cropRequests?: CropRequest[]
  /** Returned as-is to any farmer who asks for local demand. */
  demand?: CropDemand[]
  growOffers?: GrowOffer[]
  growOfferSearchResults?: GrowOfferSearchResult[]
  commitments?: CropCommitment[]
  /** Updates of every grow offer, in posting order. */
  cropUpdates?: CropUpdate[]
  cropPolls?: CropPoll[]
  cropPollSearchResults?: CropPollSearchResult[]
  cropVotes?: CropVote[]
  notifications?: Notification[]
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

export function buildCropRequest(overrides: Partial<CropRequest> = {}): CropRequest {
  return {
    id: 1,
    crop_name: 'Okra',
    quantity: 3,
    unit: 'LB',
    frequency: 'WEEKLY',
    latitude: 35.227,
    longitude: -80.843,
    radius_miles: 25,
    preferred_season: 'SUMMER',
    notes: null,
    status: 'OPEN',
    created_at: TIMESTAMP,
    covered_by_commitment: false,
    ...overrides,
  }
}

export function buildCropDemand(overrides: Partial<CropDemand> = {}): CropDemand {
  return {
    crop_name: 'Okra',
    unit: 'LB',
    customers_interested: 42,
    estimated_weekly_quantity: 126,
    one_time_quantity: 0,
    ...overrides,
  }
}

export function buildGrowOffer(overrides: Partial<GrowOffer> = {}): GrowOffer {
  return {
    id: 1,
    farm_id: 1,
    crop_name: 'Okra',
    expected_quantity: 100,
    unit: 'LB',
    estimated_price: '3.50',
    planting_date: '2026-04-15',
    expected_harvest_date: '2026-07-01',
    minimum_customers: 20,
    status: 'OPEN',
    created_at: TIMESTAMP,
    committed_customers: 12,
    committed_quantity: 40,
    ...overrides,
  }
}

export function buildGrowOfferSearchResult(
  overrides: {
    offer?: Partial<GrowOffer>
    farm?: Partial<GrowOfferSearchResult['farm']>
  } & Partial<Pick<GrowOfferSearchResult, 'distance_miles'>> = {},
): GrowOfferSearchResult {
  return {
    offer: buildGrowOffer(overrides.offer),
    farm: { id: 1, farm_name: 'Green Acres', city: 'Charlotte', state: 'NC', ...overrides.farm },
    distance_miles: overrides.distance_miles ?? 3.2,
  }
}

export function buildCropCommitment(
  overrides: Partial<Omit<CropCommitment, 'offer'>> & { offer?: Partial<GrowOffer> } = {},
): CropCommitment {
  const { offer, ...rest } = overrides
  return {
    id: 1,
    quantity: 5,
    created_at: TIMESTAMP,
    offer: buildGrowOffer(offer),
    farm: { id: 1, farm_name: 'Green Acres', city: 'Charlotte', state: 'NC' },
    ...rest,
  }
}

export function buildCropUpdate(overrides: Partial<CropUpdate> = {}): CropUpdate {
  return {
    id: 1,
    grow_offer_id: 1,
    stage: 'PLANNED',
    message: 'Seed ordered and beds prepared.',
    image_url: null,
    created_at: '2026-04-01T14:00:00Z',
    ...overrides,
  }
}

export function buildCropPoll(overrides: Partial<CropPoll> = {}): CropPoll {
  const options = overrides.options ?? [
    { id: 1, crop_name: 'Okra', votes: 6 },
    { id: 2, crop_name: 'Sweet Corn', votes: 3 },
    { id: 3, crop_name: 'Collard Greens', votes: 1 },
  ]
  return {
    id: 1,
    farm_id: 1,
    question: 'What should I grow next?',
    status: 'OPEN',
    created_at: TIMESTAMP,
    ...overrides,
    options,
    total_votes: options.reduce((total, option) => total + option.votes, 0),
  }
}

export function buildCropPollSearchResult(
  overrides: {
    poll?: Partial<CropPoll>
    farm?: Partial<CropPollSearchResult['farm']>
  } & Partial<Pick<CropPollSearchResult, 'distance_miles'>> = {},
): CropPollSearchResult {
  return {
    poll: buildCropPoll(overrides.poll),
    farm: { id: 1, farm_name: 'Green Acres', city: 'Charlotte', state: 'NC', ...overrides.farm },
    distance_miles: overrides.distance_miles ?? 3.2,
  }
}

export function buildNotification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 1,
    type: 'GROW_OFFER_CONFIRMED',
    message: 'Okra at Green Acres is confirmed. Enough customers committed, so the farm will grow it.',
    read: false,
    created_at: '2026-04-01T14:00:00Z',
    ...overrides,
  }
}

/** Stages that mean the crop is in the ground, as the API treats them. */
const GROWING_STAGES: CropStage[] = ['PLANTED', 'GERMINATED', 'GROWING', 'FLOWERING', 'HARVEST_SOON']

/** Gives a crop name the same canonical spelling the API does. */
function normalizeCropName(name: string): string {
  return name
    .split(/\s+/)
    .filter((word) => word !== '')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
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
  const cropRequests = [...(initial.cropRequests ?? [])]
  const demand = initial.demand ?? []
  const growOffers = [...(initial.growOffers ?? [])]
  const growOfferSearchResults = [...(initial.growOfferSearchResults ?? [])]
  const commitments = [...(initial.commitments ?? [])]
  const cropUpdates = [...(initial.cropUpdates ?? [])]
  const cropPolls = [...(initial.cropPolls ?? [])]
  const cropPollSearchResults = [...(initial.cropPollSearchResults ?? [])]
  const cropVotes = [...(initial.cropVotes ?? [])]
  const notifications = [...(initial.notifications ?? [])]
  const usersByToken = new Map<string, User>()
  const requests: RecordedRequest[] = []
  const searches: Record<string, string>[] = []
  const eventSearches: Record<string, string>[] = []
  const growOfferSearches: Record<string, string>[] = []
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

  function handleGrowOnDemandRequest(
    method: string,
    path: string,
    body: unknown,
    user: User | undefined,
  ) {
    const isGrowOnDemandPath = ['/api/crop-requests', '/api/demand', '/api/grow-offers', '/api/crop-commitments'].some(
      (prefix) => path.startsWith(prefix),
    )
    if (!isGrowOnDemandPath) {
      return null
    }
    if (method === 'GET' && path === '/api/grow-offers/search') {
      return jsonResponse(200, growOfferSearchResults)
    }
    if (!user) {
      return jsonResponse(401, { detail: 'Not authenticated' })
    }

    if (method === 'GET' && path === '/api/crop-requests/mine') {
      return jsonResponse(200, cropRequests)
    }
    if (method === 'POST' && path === '/api/crop-requests') {
      const details = body as NewCropRequest
      const cropName = normalizeCropName(details.crop_name)
      const hasOpenRequest = cropRequests.some(
        (request) => request.crop_name === cropName && request.status === 'OPEN',
      )
      if (hasOpenRequest) {
        return jsonResponse(409, { detail: `You already have an open request for ${cropName}` })
      }
      const request = buildCropRequest({
        ...details,
        crop_name: cropName,
        id: cropRequests.length + 1,
      })
      cropRequests.unshift(request)
      return jsonResponse(201, request)
    }
    const cancelRequestMatch = /^\/api\/crop-requests\/(\d+)\/cancel$/.exec(path)
    if (method === 'POST' && cancelRequestMatch) {
      const index = cropRequests.findIndex((request) => request.id === Number(cancelRequestMatch[1]))
      if (index === -1) {
        return jsonResponse(404, { detail: 'Crop request not found' })
      }
      cropRequests[index] = { ...cropRequests[index], status: 'CANCELLED' }
      return jsonResponse(200, cropRequests[index])
    }

    if (method === 'GET' && path === '/api/demand') {
      return jsonResponse(200, demand)
    }

    if (method === 'GET' && path === '/api/grow-offers/mine') {
      return jsonResponse(200, growOffers)
    }
    if (method === 'POST' && path === '/api/grow-offers') {
      const farm = farms.find((candidate) => candidate.owner_id === user.id)
      if (!farm) {
        return jsonResponse(409, { detail: 'Create your farm first' })
      }
      const details = body as NewGrowOffer
      const offer = buildGrowOffer({
        ...details,
        crop_name: normalizeCropName(details.crop_name),
        id: growOffers.length + 1,
        farm_id: farm.id,
        status: 'OPEN',
        committed_customers: 0,
        committed_quantity: 0,
      })
      growOffers.unshift(offer)
      return jsonResponse(201, offer)
    }
    const cancelOfferMatch = /^\/api\/grow-offers\/(\d+)\/cancel$/.exec(path)
    if (method === 'POST' && cancelOfferMatch) {
      const index = growOffers.findIndex((offer) => offer.id === Number(cancelOfferMatch[1]))
      if (index === -1) {
        return jsonResponse(404, { detail: 'Grow offer not found' })
      }
      growOffers[index] = { ...growOffers[index], status: 'CANCELLED' }
      return jsonResponse(200, growOffers[index])
    }

    if (method === 'GET' && path === '/api/crop-commitments/mine') {
      return jsonResponse(200, commitments)
    }
    if (method === 'POST' && path === '/api/crop-commitments') {
      const details = body as { grow_offer_id: number; quantity: number }
      const resultIndex = growOfferSearchResults.findIndex(
        (result) => result.offer.id === details.grow_offer_id,
      )
      if (resultIndex === -1) {
        return jsonResponse(404, { detail: 'Grow offer not found' })
      }
      const { offer, farm } = growOfferSearchResults[resultIndex]
      if (commitments.some((commitment) => commitment.offer.id === offer.id)) {
        return jsonResponse(409, { detail: 'You have already committed to this grow offer' })
      }
      const quantityRemaining = offer.expected_quantity - offer.committed_quantity
      if (details.quantity > quantityRemaining) {
        return jsonResponse(409, { detail: `Only ${quantityRemaining} left in this grow offer` })
      }
      // Like the API: the commitment that reaches the minimum confirms the offer.
      const committedCustomers = offer.committed_customers + 1
      const updatedOffer: GrowOffer = {
        ...offer,
        committed_customers: committedCustomers,
        committed_quantity: offer.committed_quantity + details.quantity,
        status:
          offer.status === 'OPEN' && committedCustomers >= offer.minimum_customers
            ? 'CONFIRMED'
            : offer.status,
      }
      growOfferSearchResults[resultIndex] = { ...growOfferSearchResults[resultIndex], offer: updatedOffer }
      const commitment: CropCommitment = {
        id: commitments.length + 1,
        quantity: details.quantity,
        created_at: TIMESTAMP,
        offer: updatedOffer,
        farm,
      }
      commitments.unshift(commitment)
      return jsonResponse(201, commitment)
    }
    return null
  }

  /** Finds a grow offer wherever a test placed it: a farmer's list, search results or commitments. */
  function findGrowOffer(offerId: number): GrowOffer | undefined {
    return (
      growOffers.find((offer) => offer.id === offerId) ??
      growOfferSearchResults.find((result) => result.offer.id === offerId)?.offer ??
      commitments.find((commitment) => commitment.offer.id === offerId)?.offer
    )
  }

  function replaceGrowOffer(updatedOffer: GrowOffer): void {
    const index = growOffers.findIndex((offer) => offer.id === updatedOffer.id)
    if (index === -1) {
      growOffers.push(updatedOffer)
    } else {
      growOffers[index] = updatedOffer
    }
  }

  function handleCropJourneyRequest(
    method: string,
    path: string,
    body: unknown,
    user: User | undefined,
  ) {
    const match = /^\/api\/grow-offers\/(\d+)(\/updates|\/complete)?$/.exec(path)
    if (!match) {
      return null
    }
    const offer = findGrowOffer(Number(match[1]))
    if (!offer) {
      return jsonResponse(404, { detail: 'Grow offer not found' })
    }
    const action = match[2]

    if (method === 'GET' && action === undefined) {
      return jsonResponse(200, {
        offer,
        farm: { id: offer.farm_id, farm_name: 'Green Acres', city: 'Charlotte', state: 'NC' },
      })
    }
    if (method === 'GET' && action === '/updates') {
      return jsonResponse(
        200,
        cropUpdates.filter((update) => update.grow_offer_id === offer.id),
      )
    }
    if (!user) {
      return jsonResponse(401, { detail: 'Not authenticated' })
    }

    if (method === 'POST' && action === '/updates') {
      const details = body as NewCropUpdate
      const update = buildCropUpdate({
        ...details,
        id: cropUpdates.length + 1,
        grow_offer_id: offer.id,
        created_at: '2026-05-01T14:00:00Z',
      })
      cropUpdates.push(update)
      // Like the API: a growing stage starts a confirmed offer growing, and READY makes it ready.
      if (details.stage === 'READY' && (offer.status === 'CONFIRMED' || offer.status === 'GROWING')) {
        replaceGrowOffer({ ...offer, status: 'READY' })
      } else if (GROWING_STAGES.includes(details.stage) && offer.status === 'CONFIRMED') {
        replaceGrowOffer({ ...offer, status: 'GROWING' })
      }
      return jsonResponse(201, update)
    }
    if (method === 'POST' && action === '/complete') {
      const completedOffer: GrowOffer = { ...offer, status: 'COMPLETED' }
      replaceGrowOffer(completedOffer)
      return jsonResponse(200, completedOffer)
    }
    return null
  }

  function handleCropPollRequest(
    method: string,
    path: string,
    body: unknown,
    user: User | undefined,
  ) {
    if (!path.startsWith('/api/crop-polls') && !path.startsWith('/api/crop-votes')) {
      return null
    }
    if (method === 'GET' && path === '/api/crop-polls/search') {
      return jsonResponse(200, cropPollSearchResults)
    }
    if (!user) {
      return jsonResponse(401, { detail: 'Not authenticated' })
    }

    if (method === 'GET' && path === '/api/crop-polls/mine') {
      return jsonResponse(200, cropPolls)
    }
    if (method === 'POST' && path === '/api/crop-polls') {
      const farm = farms.find((candidate) => candidate.owner_id === user.id)
      if (!farm) {
        return jsonResponse(409, { detail: 'Create your farm first' })
      }
      const details = body as NewCropPoll
      const poll = buildCropPoll({
        id: cropPolls.length + 1,
        farm_id: farm.id,
        question: details.question,
        options: details.options.map((cropName, index) => ({
          id: index + 1,
          crop_name: normalizeCropName(cropName),
          votes: 0,
        })),
      })
      cropPolls.unshift(poll)
      return jsonResponse(201, poll)
    }
    const closeMatch = /^\/api\/crop-polls\/(\d+)\/close$/.exec(path)
    if (method === 'POST' && closeMatch) {
      const index = cropPolls.findIndex((poll) => poll.id === Number(closeMatch[1]))
      if (index === -1) {
        return jsonResponse(404, { detail: 'Crop poll not found' })
      }
      cropPolls[index] = { ...cropPolls[index], status: 'CLOSED' }
      return jsonResponse(200, cropPolls[index])
    }

    if (method === 'GET' && path === '/api/crop-votes/mine') {
      return jsonResponse(200, cropVotes)
    }
    if (method === 'POST' && path === '/api/crop-votes') {
      const details = body as CropVote
      const resultIndex = cropPollSearchResults.findIndex(
        (result) => result.poll.id === details.poll_id,
      )
      if (resultIndex === -1) {
        return jsonResponse(404, { detail: 'Crop poll not found' })
      }
      if (cropVotes.some((vote) => vote.poll_id === details.poll_id)) {
        return jsonResponse(409, { detail: 'You have already voted in this crop poll' })
      }
      const { poll } = cropPollSearchResults[resultIndex]
      const updatedPoll = buildCropPoll({
        ...poll,
        options: poll.options.map((option) =>
          option.id === details.option_id ? { ...option, votes: option.votes + 1 } : option,
        ),
      })
      cropPollSearchResults[resultIndex] = { ...cropPollSearchResults[resultIndex], poll: updatedPoll }
      cropVotes.unshift({ poll_id: details.poll_id, option_id: details.option_id })
      return jsonResponse(201, { ...details, poll: updatedPoll })
    }
    return null
  }

  function handleNotificationRequest(method: string, path: string, user: User | undefined) {
    if (!path.startsWith('/api/notifications')) {
      return null
    }
    if (!user) {
      return jsonResponse(401, { detail: 'Not authenticated' })
    }

    if (method === 'GET' && path === '/api/notifications') {
      return jsonResponse(200, notifications)
    }
    if (method === 'GET' && path === '/api/notifications/unread-count') {
      return jsonResponse(200, {
        unread: notifications.filter((notification) => !notification.read).length,
      })
    }
    if (method === 'POST' && path === '/api/notifications/read-all') {
      notifications.forEach((notification, index) => {
        notifications[index] = { ...notification, read: true }
      })
      return new Response(null, { status: 204 })
    }
    const readMatch = /^\/api\/notifications\/(\d+)\/read$/.exec(path)
    if (method === 'POST' && readMatch) {
      const index = notifications.findIndex(
        (notification) => notification.id === Number(readMatch[1]),
      )
      if (index === -1) {
        return jsonResponse(404, { detail: 'Notification not found' })
      }
      notifications[index] = { ...notifications[index], read: true }
      return jsonResponse(200, notifications[index])
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
    if (path === '/api/grow-offers/search') {
      growOfferSearches.push(Object.fromEntries(url.searchParams))
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
      handleCropJourneyRequest(method, path, body, user) ??
      handleGrowOnDemandRequest(method, path, body, user) ??
      handleCropPollRequest(method, path, body, user) ??
      handleNotificationRequest(method, path, user) ??
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
    /** The query parameters of every grow offer search, in order. */
    growOfferSearches,
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
