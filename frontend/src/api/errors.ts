import { ApiError } from './client.ts'

/** Text safe to show a user for any failure thrown while calling the API. */
export function describeApiError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }
  return 'Something went wrong. Please try again.'
}
