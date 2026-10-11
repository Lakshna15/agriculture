const SEARCH_LOCATION_STORAGE_KEY = 'farm2local.searchLocation'

export type SearchLocation = { latitude: string; longitude: string }

const NO_LOCATION: SearchLocation = { latitude: '', longitude: '' }

// The last location a customer searched from is remembered for the rest of
// the browser tab's life, so the product and experience searches share it.
// It stays in the browser and is cleared when the tab closes.

export function readSearchLocation(): SearchLocation {
  try {
    const stored = window.sessionStorage.getItem(SEARCH_LOCATION_STORAGE_KEY)
    if (stored === null) {
      return NO_LOCATION
    }
    const parsed: unknown = JSON.parse(stored)
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      'latitude' in parsed &&
      'longitude' in parsed &&
      typeof parsed.latitude === 'string' &&
      typeof parsed.longitude === 'string'
    ) {
      return { latitude: parsed.latitude, longitude: parsed.longitude }
    }
    return NO_LOCATION
  } catch {
    return NO_LOCATION
  }
}

export function storeSearchLocation(location: SearchLocation): void {
  try {
    window.sessionStorage.setItem(SEARCH_LOCATION_STORAGE_KEY, JSON.stringify(location))
  } catch {
    // Storage can be unavailable; the location then has to be typed again.
  }
}
