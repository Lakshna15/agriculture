export const ACCESS_TOKEN_STORAGE_KEY = 'farm2local.accessToken'

// Storage access can throw when the browser blocks it (for example in some
// private modes). The session then simply lasts until the page is closed.

export function readStoredAccessToken(): string | null {
  try {
    return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function storeAccessToken(accessToken: string): void {
  try {
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken)
  } catch {
    // Nothing to do: the token is still held in memory for this page.
  }
}

export function clearStoredAccessToken(): void {
  try {
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
  } catch {
    // Nothing to do.
  }
}
