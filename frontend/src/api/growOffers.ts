import { apiRequest } from './client.ts'
import type { ProductUnit } from './products.ts'

export type GrowOfferStatus =
  | 'OPEN'
  | 'CONFIRMED'
  | 'GROWING'
  | 'READY'
  | 'COMPLETED'
  | 'CANCELLED'

export type GrowOffer = {
  id: number
  farm_id: number
  crop_name: string
  expected_quantity: number
  unit: ProductUnit
  /** Per unit, as text such as "3.50". An estimate, because the crop is not grown yet. */
  estimated_price: string
  /** ISO calendar dates, for example "2026-06-01". */
  planting_date: string
  expected_harvest_date: string
  /** The offer is confirmed once this many customers have committed. */
  minimum_customers: number
  status: GrowOfferStatus
  created_at: string
  committed_customers: number
  committed_quantity: number
}

export type NewGrowOffer = Pick<
  GrowOffer,
  | 'crop_name'
  | 'expected_quantity'
  | 'unit'
  | 'estimated_price'
  | 'planting_date'
  | 'expected_harvest_date'
  | 'minimum_customers'
>

export type GrowOfferFarm = { id: number; farm_name: string; city: string; state: string }

export type GrowOfferSearchCriteria = {
  latitude: number
  longitude: number
  radiusMiles: number
  /** Text to look for in crop names. Empty means every crop. */
  crop: string
}

export type GrowOfferSearchResult = {
  offer: GrowOffer
  farm: GrowOfferFarm
  distance_miles: number
}

export type CropCommitment = {
  id: number
  quantity: number
  created_at: string
  offer: GrowOffer
  farm: GrowOfferFarm
}

export function createGrowOffer(accessToken: string, offer: NewGrowOffer): Promise<GrowOffer> {
  return apiRequest<GrowOffer>('/api/grow-offers', { method: 'POST', body: offer, accessToken })
}

export function fetchMyGrowOffers(accessToken: string): Promise<GrowOffer[]> {
  return apiRequest<GrowOffer[]>('/api/grow-offers/mine', { accessToken })
}

export function cancelGrowOffer(accessToken: string, offerId: number): Promise<GrowOffer> {
  return apiRequest<GrowOffer>(`/api/grow-offers/${offerId}/cancel`, {
    method: 'POST',
    accessToken,
  })
}

export function searchGrowOffers(
  criteria: GrowOfferSearchCriteria,
): Promise<GrowOfferSearchResult[]> {
  const params = new URLSearchParams({
    latitude: String(criteria.latitude),
    longitude: String(criteria.longitude),
    radius_miles: String(criteria.radiusMiles),
  })
  if (criteria.crop.trim() !== '') {
    params.set('crop', criteria.crop.trim())
  }
  return apiRequest<GrowOfferSearchResult[]>(`/api/grow-offers/search?${params}`)
}

export function commitToGrowOffer(
  accessToken: string,
  offerId: number,
  quantity: number,
): Promise<CropCommitment> {
  return apiRequest<CropCommitment>('/api/crop-commitments', {
    method: 'POST',
    body: { grow_offer_id: offerId, quantity },
    accessToken,
  })
}

export function fetchMyCommitments(accessToken: string): Promise<CropCommitment[]> {
  return apiRequest<CropCommitment[]>('/api/crop-commitments/mine', { accessToken })
}
