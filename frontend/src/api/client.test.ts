import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiRequest, setUnauthorizedHandler } from './client.ts'
import { describeApiError } from './errors.ts'

function respondWith(status: number, body?: unknown): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(async () =>
    body === undefined
      ? new Response(null, { status })
      : new Response(typeof body === 'string' ? body : JSON.stringify(body), {
          status,
          headers: { 'Content-Type': 'application/json' },
        }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function failureOf(request: Promise<unknown>): Promise<ApiError> {
  try {
    await request
  } catch (error) {
    if (error instanceof ApiError) {
      return error
    }
    throw error
  }
  throw new Error('Expected the request to fail')
}

afterEach(() => {
  setUnauthorizedHandler(null)
})

describe('apiRequest', () => {
  it('sends a JSON body and the access token, and returns the parsed response', async () => {
    const fetchMock = respondWith(201, { id: 7 })

    const result = await apiRequest<{ id: number }>('/api/things', {
      method: 'POST',
      body: { name: 'Kale' },
      accessToken: 'token-123',
    })

    expect(result).toEqual({ id: 7 })
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(init.headers)
    expect(path).toBe('/api/things')
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"name":"Kale"}')
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Authorization')).toBe('Bearer token-123')
  })

  it('sends no body, content type or authorization when there are none', async () => {
    const fetchMock = respondWith(200, [])

    await apiRequest('/api/things')

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(init.headers)
    expect(init.method).toBe('GET')
    expect(init.body).toBeUndefined()
    expect(headers.has('Content-Type')).toBe(false)
    expect(headers.has('Authorization')).toBe(false)
  })

  it('returns nothing for 204 No Content', async () => {
    respondWith(204)

    await expect(apiRequest('/api/things/1', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('uses the message the API gives for an error', async () => {
    respondWith(409, { detail: 'An account with this email already exists' })

    const error = await failureOf(apiRequest('/api/auth/register', { method: 'POST', body: {} }))

    expect(error.status).toBe(409)
    expect(error.message).toBe('An account with this email already exists')
  })

  it('names each field that failed validation', async () => {
    respondWith(422, {
      detail: [
        { type: 'string_too_short', loc: ['body', 'password'], msg: 'String should have at least 8 characters' },
        { type: 'missing', loc: ['body'], msg: 'Field required' },
        { type: 'value_error', loc: ['body', 'items', 0] },
      ],
    })

    const error = await failureOf(apiRequest('/api/auth/register', { method: 'POST', body: {} }))

    expect(error.message).toBe(
      'password: String should have at least 8 characters. Field required. Invalid value',
    )
  })

  it.each([
    ['a body that is not JSON', 'Bad gateway'],
    ['a body without a detail', { error: 'nope' }],
    ['an empty list of issues', { detail: [] }],
  ])('falls back to a general message for %s', async (_case, body) => {
    respondWith(502, body)

    const error = await failureOf(apiRequest('/api/things'))

    expect(error.message).toBe('The request failed (status 502).')
  })

  it('reports an unreachable server as status 0', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )

    const error = await failureOf(apiRequest('/api/things'))

    expect(error.status).toBe(0)
    expect(error.message).toBe('Unable to reach the server. Check your connection and try again.')
  })

  it('ends the session when a request made with a token is rejected as unauthorized', async () => {
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    respondWith(401, { detail: 'Could not validate credentials' })

    await failureOf(apiRequest('/api/auth/me', { accessToken: 'expired-token' }))

    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('does not end a session for a failed login, which carries no token', async () => {
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    respondWith(401, { detail: 'Incorrect email or password' })

    const error = await failureOf(apiRequest('/api/auth/login', { method: 'POST', body: {} }))

    expect(error.message).toBe('Incorrect email or password')
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it('does not end the session for a refusal that is not about the token', async () => {
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    respondWith(403, { detail: 'Only farmers can do this' })

    await failureOf(apiRequest('/api/farms', { method: 'POST', body: {}, accessToken: 'token' }))

    expect(onUnauthorized).not.toHaveBeenCalled()
  })
})

describe('describeApiError', () => {
  it('shows the message of an API error', () => {
    expect(describeApiError(new ApiError(404, 'Product not found'))).toBe('Product not found')
  })

  it('hides the details of any other failure', () => {
    expect(describeApiError(new TypeError('undefined is not a function'))).toBe(
      'Something went wrong. Please try again.',
    )
  })
})
