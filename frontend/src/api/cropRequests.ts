import { apiRequest } from './client.ts'
import type { ProductUnit } from './products.ts'

export type RequestFrequency = 'ONE_TIME' | 'WEEKLY' | 'MONTHLY'

export type Season = 'SPRING' | 'SUMMER' | 'FALL' | 'WINTER'

export type CropRequestStatus = 'OPEN' | 'CANCELLED'

export type CropRequest = {
  id: number
  crop_name: string
  quantity: number
  unit: ProductUnit
  frequency: RequestFrequency
  latitude: number
  longitude: number
  /** How far the customer is willing to travel for the crop. */
  radius_miles: number
  preferred_season: Season | null
  notes: string | null
  status: CropRequestStatus
  created_at: string
  /** True once the customer has joined an active grow offer for this crop. */
  covered_by_commitment: boolean
}

export type NewCropRequest = Omit<
  CropRequest,
  'id' | 'status' | 'created_at' | 'covered_by_commitment'
>

/**
 * Open requests for one crop near a farm, added together. This is all a
 * farmer receives about demand: there is nothing here about any one customer.
 */
export type CropDemand = {
  crop_name: string
  unit: ProductUnit
  customers_interested: number
  estimated_weekly_quantity: number
  one_time_quantity: number
}

export function createCropRequest(
  accessToken: string,
  request: NewCropRequest,
): Promise<CropRequest> {
  return apiRequest<CropRequest>('/api/crop-requests', {
    method: 'POST',
    body: request,
    accessToken,
  })
}

export function fetchMyCropRequests(accessToken: string): Promise<CropRequest[]> {
  return apiRequest<CropRequest[]>('/api/crop-requests/mine', { accessToken })
}

export function cancelCropRequest(accessToken: string, requestId: number): Promise<CropRequest> {
  return apiRequest<CropRequest>(`/api/crop-requests/${requestId}/cancel`, {
    method: 'POST',
    accessToken,
  })
}

export function fetchLocalDemand(accessToken: string): Promise<CropDemand[]> {
  return apiRequest<CropDemand[]>('/api/demand', { accessToken })
}
