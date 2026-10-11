export const LATITUDE_LIMIT = 90
export const LONGITUDE_LIMIT = 180

/** Reads a coordinate typed by the user, or null if it is not a number within ±limit. */
export function parseCoordinate(text: string, limit: number): number | null {
  const value = Number(text)
  const isValid = text.trim() !== '' && Number.isFinite(value) && Math.abs(value) <= limit
  return isValid ? value : null
}

export const latitudeErrorMessage = `Latitude must be a number between -${LATITUDE_LIMIT} and ${LATITUDE_LIMIT}.`
export const longitudeErrorMessage = `Longitude must be a number between -${LONGITUDE_LIMIT} and ${LONGITUDE_LIMIT}.`
