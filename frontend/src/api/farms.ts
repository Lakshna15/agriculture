import { ApiError, apiRequest } from './client.ts'

export type Farm = {
  id: number
  owner_id: number
  farm_name: string
  description: string | null
  address: string
  city: string
  state: string
  zip_code: string
  latitude: number
  longitude: number
  phone: string | null
  pickup_available: boolean
  delivery_available: boolean
  created_at: string
  updated_at: string
}

/** The fields a farmer can set. The server assigns the rest. */
export type FarmDetails = Omit<Farm, 'id' | 'owner_id' | 'created_at' | 'updated_at'>

/** Resolves to null when the signed-in farmer has not created a farm yet. */
export async function fetchMyFarm(accessToken: string): Promise<Farm | null> {
  try {
    return await apiRequest<Farm>('/api/farms/me', { accessToken })
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null
    }
    throw error
  }
}

export function createFarm(accessToken: string, details: FarmDetails): Promise<Farm> {
  return apiRequest<Farm>('/api/farms', { method: 'POST', body: details, accessToken })
}

export function updateFarm(
  accessToken: string,
  farmId: number,
  details: FarmDetails,
): Promise<Farm> {
  return apiRequest<Farm>(`/api/farms/${farmId}`, { method: 'PUT', body: details, accessToken })
}
