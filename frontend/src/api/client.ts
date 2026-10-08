export class ApiError extends Error {
  /** HTTP status of the failed response, or 0 when the server could not be reached. */
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

let unauthorizedHandler: (() => void) | null = null

/**
 * Registers what to do when the server rejects a token that was sent with a
 * request. The auth provider uses this to end the session from one place, so
 * an expired token signs the user out wherever the request was made.
 */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

type ApiRequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  accessToken?: string | null
}

type ValidationIssue = { loc?: unknown[]; msg?: string }

function describeValidationIssue(issue: ValidationIssue): string {
  const field = issue.loc?.at(-1)
  const message = issue.msg ?? 'Invalid value'
  return typeof field === 'string' ? `${field}: ${message}` : message
}

async function readErrorMessage(response: Response): Promise<string> {
  const fallbackMessage = `The request failed (status ${response.status}).`
  try {
    const body: unknown = await response.json()
    if (typeof body !== 'object' || body === null || !('detail' in body)) {
      return fallbackMessage
    }
    // FastAPI sends a string for raised errors and a list of issues for validation failures.
    if (typeof body.detail === 'string') {
      return body.detail
    }
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      return body.detail.map(describeValidationIssue).join('. ')
    }
    return fallbackMessage
  } catch {
    return fallbackMessage
  }
}

export async function apiRequest<ResponseBody>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<ResponseBody> {
  const headers = new Headers({ Accept: 'application/json' })
  if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }
  if (options.accessToken) {
    headers.set('Authorization', `Bearer ${options.accessToken}`)
  }

  let response: Response
  try {
    response = await fetch(path, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch {
    throw new ApiError(0, 'Unable to reach the server. Check your connection and try again.')
  }

  if (!response.ok) {
    // A 401 without a token is a failed login, not an ended session.
    if (response.status === 401 && options.accessToken) {
      unauthorizedHandler?.()
    }
    throw new ApiError(response.status, await readErrorMessage(response))
  }
  return (await response.json()) as ResponseBody
}
