import { vi } from 'vitest'
import type { User, UserRole } from '../api/auth.ts'
import type { Farm, FarmDetails } from '../api/farms.ts'
import { ACCESS_TOKEN_STORAGE_KEY } from '../auth/tokenStorage.ts'

type FakeAccount = { user: User; password: string }

type RecordedRequest = { method: string; path: string; body: unknown }

type ForcedFailure = { method: string; path: string; status: number; detail: string }

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

/**
 * Replaces fetch with an in-memory stand-in for the backend. It follows the
 * real API's status codes and error bodies so the tests exercise the same
 * paths the application takes against the server.
 */
export function installFakeApi(initial: { accounts?: FakeAccount[]; farms?: Farm[] } = {}) {
  const accounts = [...(initial.accounts ?? [])]
  const farms = [...(initial.farms ?? [])]
  const usersByToken = new Map<string, User>()
  const requests: RecordedRequest[] = []
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

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'
    const body: unknown = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
    requests.push({ method, path, body })

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
      jsonResponse(404, { detail: 'Not Found' })
    )
  })

  vi.stubGlobal('fetch', fetchMock)

  return {
    requests,
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
